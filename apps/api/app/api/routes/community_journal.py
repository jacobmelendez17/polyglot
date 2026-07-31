"""Community journal endpoints (spec §7). Auth required throughout."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.capabilities import Capability, has_capability
from app.auth.deps import get_current_user, require
from app.db.session import get_db
from app.models.identity import User
from app.services import community_journal as svc

router = APIRouter(prefix="/api/v1", tags=["community-journals"])


def _mod(user: User) -> bool:
    return has_capability(user.role, Capability.forum_moderate)


def _http(e: svc.CommunityJournalError) -> HTTPException:
    return HTTPException(status_code=e.status,
                        detail={"error": {"code": e.code, "message": e.message}})


# --- schemas ---------------------------------------------------------------

class MyEntryOut(BaseModel):
    id: str
    title: str
    excerpt: str
    shared: bool
    share_hidden: bool
    shared_at: str | None = None
    feedback_count: int


class FeedItemOut(BaseModel):
    id: str
    author: str
    title: str
    excerpt: str
    shared_at: str | None = None
    feedback_count: int


class FeedbackOut(BaseModel):
    id: str
    author: str
    body: str
    hidden: bool
    created_at: str | None = None


class EntryOut(BaseModel):
    id: str
    author: str
    title: str
    body: str
    shared_at: str | None = None
    share_hidden: bool
    is_owner: bool
    feedback: list[FeedbackOut]


class ShareOut(BaseModel):
    id: str
    shared: bool


class FeedbackIn(BaseModel):
    body: str = Field(min_length=1, max_length=3000)


class HideIn(BaseModel):
    hidden: bool
    reason: str | None = Field(default=None, max_length=300)


# --- owner surface ---------------------------------------------------------

@router.get("/me/community-journals/mine", response_model=list[MyEntryOut])
def mine(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.my_entries(db, user_id=user.id)


@router.post("/me/community-journals/{entry_id}/share", response_model=ShareOut)
def share(entry_id: str = Path(max_length=64),
          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = svc.share(db, user_id=user.id, entry_id=entry_id)
    except svc.CommunityJournalError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result


@router.post("/me/community-journals/{entry_id}/unshare", response_model=ShareOut)
def unshare(entry_id: str = Path(max_length=64),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = svc.unshare(db, user_id=user.id, entry_id=entry_id)
    except svc.CommunityJournalError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result


# --- community surface -----------------------------------------------------

@router.get("/community/journals", response_model=list[FeedItemOut])
def feed(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return svc.community_feed(db)


@router.get("/community/journals/{entry_id}", response_model=EntryOut)
def entry(entry_id: str = Path(max_length=64),
          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return svc.get_shared_entry(db, viewer_id=user.id, viewer_is_mod=_mod(user),
                                    entry_id=entry_id)
    except svc.CommunityJournalError as e:
        raise _http(e) from e


@router.post("/community/journals/{entry_id}/feedback", response_model=FeedbackOut)
def feedback(body: FeedbackIn, entry_id: str = Path(max_length=64),
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = svc.post_feedback(db, author_id=user.id, entry_id=entry_id, body=body.body)
    except svc.CommunityJournalError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result


# --- moderation (forum_moderate) -------------------------------------------

@router.post("/community/feedback/{feedback_id}/hide")
def hide_feedback(body: HideIn, feedback_id: str = Path(max_length=64),
                  db: Session = Depends(get_db),
                  _: User = Depends(require(Capability.forum_moderate))):
    try:
        result = svc.set_feedback_hidden(db, feedback_id=feedback_id,
                                         hidden=body.hidden, reason=body.reason)
    except svc.CommunityJournalError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result


@router.post("/community/journals/{entry_id}/hide")
def hide_entry(body: HideIn, entry_id: str = Path(max_length=64),
               db: Session = Depends(get_db),
               _: User = Depends(require(Capability.forum_moderate))):
    try:
        result = svc.set_entry_hidden(db, entry_id=entry_id,
                                      hidden=body.hidden, reason=body.reason)
    except svc.CommunityJournalError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result
