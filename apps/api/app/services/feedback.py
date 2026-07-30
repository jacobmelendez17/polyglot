"""Feedback / support service (spec §22, §30).

A user files a ticket from anywhere in the app; the ticket captures the route
and browser so a bug can be reproduced, is stored, and triggers a best-effort
notification email to the owner. Admins list tickets filtered by state/pinned,
respond, and pin.

The email is a *notification*, not the record: the ticket row is the durable
artifact (and shows in the admin tab and Mailpit locally), so if email delivery
isn't configured or fails, ticket creation still succeeds. `email_sent_at` is
stamped only when a send actually goes through.
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import feedback as rules
from app.models.identity import Profile, User
from app.models.platform import FeedbackTicket

log = logging.getLogger(__name__)

# Owner inbox for support/feedback (§30). Overridable via env FEEDBACK_EMAIL.
DEFAULT_FEEDBACK_EMAIL = "jacobmelen17@gmail.com"

MAX_PAGE = 100


class FeedbackError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.isoformat()


# --- create ---------------------------------------------------------------

def submit(
    db: Session, *, user: User, category: str, body: str, route: str = "",
    browser: str = "", settings=None, now: dt.datetime | None = None,
) -> dict:
    now = now or _now()

    # Rate limit: recent tickets from this user.
    since = now - rules.WINDOW
    recent_times = db.execute(
        select(FeedbackTicket.created_at).where(
            FeedbackTicket.user_id == user.id, FeedbackTicket.created_at >= since,
        )
    ).scalars().all()
    if not rules.can_submit([t for t in recent_times if t], now):
        raise FeedbackError(
            "Thanks — you've sent a few already. Please try again a little later.",
            "rate_limited", 429,
        )

    clean_body = rules.sanitize_body(body)
    if not rules.is_valid_body(clean_body):
        raise FeedbackError("Please describe your feedback.", "invalid_body", 400)

    ticket = FeedbackTicket(
        user_id=user.id,
        category=rules.normalize_category(category),
        route=rules.sanitize_meta(route, max_length=rules.ROUTE_MAX),
        browser=rules.sanitize_meta(browser, max_length=rules.BROWSER_MAX),
        body=clean_body,
        state="unanswered",
    )
    db.add(ticket)
    db.flush()

    if _notify_owner(ticket, user=user, settings=settings):
        ticket.email_sent_at = now
    db.flush()

    return {"id": str(ticket.id), "state": ticket.state}


def _notify_owner(ticket: FeedbackTicket, *, user: User, settings) -> bool:
    """Best-effort email to the owner. Returns True if a send went through.

    Deliberately defensive: the ticket is already saved, so any failure here
    (no provider configured, interface mismatch) is logged and swallowed rather
    than failing the user's submission.
    """
    to_addr = (getattr(settings, "feedback_email", "") or DEFAULT_FEEDBACK_EMAIL)
    subject = f"[polyglot feedback] {ticket.category}: {ticket.body[:60]}"
    lines = [
        f"New {ticket.category} from {user.email}",
        f"route: {ticket.route or '—'}",
        f"browser: {ticket.browser or '—'}",
        "",
        ticket.body,
    ]
    text = "\n".join(lines)
    try:
        from app.services import email as email_mod  # slice 11 provider
        provider = email_mod.build_email_provider(settings)
        # Support a couple of provider shapes without hard-coupling.
        if hasattr(provider, "send"):
            try:
                msg = email_mod.EmailMessage(
                    to=to_addr, subject=subject, text=text,
                )  # type: ignore[attr-defined]
                provider.send(msg)
            except (AttributeError, TypeError):
                provider.send(to=to_addr, subject=subject, body=text)  # type: ignore
            return True
    except Exception:  # pragma: no cover - provider optional/undetermined
        log.info("feedback.email_skipped", extra={"ticket": str(ticket.id)})
    return False


# --- admin reads ----------------------------------------------------------

def list_tickets(
    db: Session, *, state: str | None = None, pinned: bool | None = None,
    limit: int = 50, offset: int = 0,
) -> dict:
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))

    where = []
    if state in ("unanswered", "answered"):
        where.append(FeedbackTicket.state == state)
    if pinned is not None:
        where.append(FeedbackTicket.pinned.is_(bool(pinned)))

    total = db.execute(
        select(func.count(FeedbackTicket.id)).where(*where)
    ).scalar_one()
    rows = db.execute(
        select(FeedbackTicket, Profile.display_name, User.email)
        .outerjoin(Profile, Profile.user_id == FeedbackTicket.user_id)
        .outerjoin(User, User.id == FeedbackTicket.user_id)
        .where(*where)
        # pinned first, then newest
        .order_by(FeedbackTicket.pinned.desc(), FeedbackTicket.created_at.desc())
        .limit(limit).offset(offset)
    ).all()

    return {
        "total": int(total or 0), "limit": limit, "offset": offset,
        "tickets": [_ticket_out(t, name, email) for t, name, email in rows],
    }


def _ticket_out(t: FeedbackTicket, name: str | None, email: str | None) -> dict:
    return {
        "id": str(t.id),
        "category": t.category,
        "body": t.body or "",
        "route": t.route or "",
        "browser": t.browser or "",
        "state": t.state,
        "pinned": bool(t.pinned),
        "from_name": name or "someone",
        "from_email": email or "",
        "admin_response": getattr(t, "admin_response", "") or "",
        "responded_at": _iso(getattr(t, "responded_at", None)),
        "email_sent": t.email_sent_at is not None,
        "created_at": _iso(t.created_at),
    }


def counts(db: Session) -> dict:
    """Tab badge counts for the admin inbox."""
    def n(*where):
        return int(db.execute(
            select(func.count(FeedbackTicket.id)).where(*where)
        ).scalar_one() or 0)
    return {
        "unanswered": n(FeedbackTicket.state == "unanswered"),
        "answered": n(FeedbackTicket.state == "answered"),
        "pinned": n(FeedbackTicket.pinned.is_(True)),
    }


# --- admin writes ---------------------------------------------------------

def respond(
    db: Session, *, actor: User, ticket_id: str, response: str,
    now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    ticket = _get(db, ticket_id)
    clean = rules.sanitize_body(response)
    if not clean:
        raise FeedbackError("Write a response first.", "invalid_response", 400)
    ticket.admin_response = clean
    ticket.responded_at = now
    ticket.responded_by = actor.id
    ticket.state = "answered"
    db.flush()
    return _ticket_out(ticket, None, None)


def set_pin(db: Session, *, ticket_id: str, pinned: bool) -> dict:
    ticket = _get(db, ticket_id)
    ticket.pinned = bool(pinned)
    db.flush()
    return _ticket_out(ticket, None, None)


def set_state(db: Session, *, ticket_id: str, state: str) -> dict:
    if state not in ("unanswered", "answered"):
        raise FeedbackError("Unknown state.", "invalid_state", 400)
    ticket = _get(db, ticket_id)
    ticket.state = state
    db.flush()
    return _ticket_out(ticket, None, None)


def _get(db: Session, ticket_id: str) -> FeedbackTicket:
    try:
        tid = uuid.UUID(str(ticket_id))
    except (ValueError, AttributeError):
        raise FeedbackError("Ticket not found.", "not_found", 404) from None
    ticket = db.get(FeedbackTicket, tid)
    if ticket is None:
        raise FeedbackError("Ticket not found.", "not_found", 404)
    return ticket
