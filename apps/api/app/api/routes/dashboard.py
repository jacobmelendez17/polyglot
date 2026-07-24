"""Dashboard layout + guided tour endpoints.

Everything is scoped to the authenticated user: there is no path parameter for
a user id anywhere in this file, so one learner can never read or write
another's dashboard.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.routes.dashboard_schemas import (
    DashboardOut,
    LayoutIn,
    TourCompleteIn,
    TourStateOut,
    TourStepIn,
)
from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import dashboard as dash_svc

router = APIRouter(prefix="/api/v1/me", tags=["dashboard"])

TOUR_KEY = Path(pattern="^[a-z_]{1,40}$")


def _http(err: dash_svc.DashboardError) -> HTTPException:
    return HTTPException(
        status_code=err.status,
        detail={"error": {"code": err.code, "message": err.message}},
    )


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return dash_svc.dashboard_view(db, user_id=user.id)


@router.put("/dashboard", response_model=DashboardOut)
def put_dashboard(
    body: LayoutIn,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    dash_svc.save_layout(
        db, user_id=user.id,
        raw={"widgets": [w.model_dump() for w in body.widgets]},
    )
    db.commit()
    return dash_svc.dashboard_view(db, user_id=user.id)


@router.post("/dashboard/reset", response_model=DashboardOut)
def reset_dashboard(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    dash_svc.reset_layout(db, user_id=user.id)
    db.commit()
    return dash_svc.dashboard_view(db, user_id=user.id)


@router.get("/tours/{tour_key}", response_model=TourStateOut)
def get_tour(
    tour_key: str = TOUR_KEY,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    try:
        return dash_svc.tour_state(db, user_id=user.id, tour_key=tour_key)
    except dash_svc.DashboardError as e:
        raise _http(e) from e


@router.post("/tours/{tour_key}/step", response_model=TourStateOut)
def post_tour_step(
    body: TourStepIn,
    tour_key: str = TOUR_KEY,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    try:
        state = dash_svc.record_step(
            db, user_id=user.id, tour_key=tour_key, step_index=body.step_index
        )
    except dash_svc.DashboardError as e:
        raise _http(e) from e
    db.commit()
    return state


@router.post("/tours/{tour_key}/complete", response_model=TourStateOut)
def post_tour_complete(
    body: TourCompleteIn,
    tour_key: str = TOUR_KEY,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    try:
        state = dash_svc.complete_tour(
            db, user_id=user.id, tour_key=tour_key, skipped=body.skipped
        )
    except dash_svc.DashboardError as e:
        raise _http(e) from e
    db.commit()
    return state


@router.post("/tours/{tour_key}/restart", response_model=TourStateOut)
def post_tour_restart(
    tour_key: str = TOUR_KEY,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    try:
        state = dash_svc.restart_tour(db, user_id=user.id, tour_key=tour_key)
    except dash_svc.DashboardError as e:
        raise _http(e) from e
    db.commit()
    return state
