"""Email delivery, behind a provider interface (PLANNING §5, §33 pattern).

Same shape as the audio/speech provider abstractions: one interface, a couple of
backends, chosen by config. Swapping Mailpit for a production provider (Resend,
Postmark, SES) is a config change and a new subclass, never an edit to the
call sites.

Backends:

  * **SMTP** — talks to Mailpit locally (port 1025, no auth) and to a real relay
    in production with the same code.
  * **Console** — writes the message to the log. The default when no SMTP host
    is configured, so a fresh checkout can exercise the whole reset flow without
    any mail setup at all.
  * **Memory** — captures sent messages in a list for tests to assert against.

Nothing here logs the message body or the token: an email body carries a
one-time credential, and logging it would undo the point of hashing it in the
database (§25 — never log tokens).
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage

log = logging.getLogger(__name__)


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str | None = None


class EmailProvider:
    """The interface every backend implements."""

    def send(self, message: OutgoingEmail) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    """Logs that an email would be sent — never its body or any token in it."""

    def send(self, message: OutgoingEmail) -> None:
        log.info(
            "email.console_send", extra={"to": message.to, "subject": message.subject}
        )


@dataclass
class MemoryEmailProvider(EmailProvider):
    """Captures messages for tests."""

    sent: list[OutgoingEmail] = field(default_factory=list)

    def send(self, message: OutgoingEmail) -> None:
        self.sent.append(message)


@dataclass
class SmtpEmailProvider(EmailProvider):
    host: str
    port: int = 1025
    username: str = ""
    password: str = ""
    use_tls: bool = False
    from_address: str = "polyglot <no-reply@polyglot.local>"

    def send(self, message: OutgoingEmail) -> None:
        email = EmailMessage()
        email["From"] = self.from_address
        email["To"] = message.to
        email["Subject"] = message.subject
        email.set_content(message.text)
        if message.html:
            email.add_alternative(message.html, subtype="html")

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                if self.use_tls:
                    server.starttls(context=ssl.create_default_context())
                if self.username:
                    server.login(self.username, self.password)
                server.send_message(email)
        except OSError as exc:
            # A mail outage must not take a request down with it. The caller
            # decides what to surface; for reset/verify we stay deliberately
            # vague to the user regardless (see the service layer).
            log.error("email.smtp_failed", extra={"to": message.to, "error": str(exc)})
            raise EmailDeliveryError("Could not send the email.") from exc


class EmailDeliveryError(Exception):
    pass


def build_provider(settings) -> EmailProvider:
    """Pick a backend from config. No SMTP host → console, so a bare checkout
    still runs every flow end to end."""
    backend = (getattr(settings, "email_backend", "") or "").strip().lower()
    host = getattr(settings, "smtp_host", "") or ""

    if backend == "memory":
        return MemoryEmailProvider()
    if backend == "console" or (not backend and not host):
        return ConsoleEmailProvider()
    if not host:
        return ConsoleEmailProvider()
    return SmtpEmailProvider(
        host=host,
        port=int(getattr(settings, "smtp_port", 1025) or 1025),
        username=getattr(settings, "smtp_username", "") or "",
        password=getattr(settings, "smtp_password", "") or "",
        use_tls=bool(getattr(settings, "smtp_use_tls", False)),
        from_address=getattr(settings, "email_from", "")
        or "polyglot <no-reply@polyglot.local>",
    )
