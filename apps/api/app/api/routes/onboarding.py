"""Onboarding completion (spec §14).

The onboarding slides are "skippable but not replayable" — so completion has to
persist somewhere durable, not just in the browser. This records it on the
profile (`onboarding_completed_at`), which `/me` now reports so the app can route
a signed-in user to the intro exactly once.

Resetting progress (admin dev sandbox) clears that stamp, which is what lets you
see the intro again on your next sign-in.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.feedback_schemas import OnboardingStateOut
from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import Profile, User

router = APIRouter(prefix="/api/v1/me/onboarding", tags=["onboarding"])


@router.get("", response_model=OnboardingStateOut)
def onboarding_state(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    profile = db.get(Profile, user.id)
    completed = bool(profile and profile.onboarding_completed_at is not None)
    return OnboardingStateOut(completed=completed)


@router.post("/complete", response_model=OnboardingStateOut)
def complete_onboarding(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    profile = db.get(Profile, user.id)
    if profile is not None and profile.onboarding_completed_at is None:
        profile.onboarding_completed_at = dt.datetime.now(tz=dt.timezone.utc)
        db.commit()
    return OnboardingStateOut(completed=True)
