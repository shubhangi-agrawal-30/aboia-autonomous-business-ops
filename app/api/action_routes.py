from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.db.database import SessionLocal
from app.db.models import Action


router = APIRouter(
    prefix="/actions",
    tags=["Actions"]
)


# ---------------------------------------------------------
# GET ALL ACTIONS (with filtering + pagination)
# ---------------------------------------------------------
@router.get("/")
def get_all_actions(
    status: Optional[str] = Query(None),
    approval_status: Optional[str] = Query(None),
    sla_status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Retrieve actions with optional filtering and pagination.
    """

    db = SessionLocal()

    try:
        base_query = db.query(Action)

        # Apply filters
        if status:
            base_query = base_query.filter(Action.status == status)

        if approval_status:
            base_query = base_query.filter(Action.approval_status == approval_status)

        if sla_status:
            base_query = base_query.filter(Action.sla_status == sla_status)

        if priority:
            base_query = base_query.filter(Action.priority == priority)

        if owner:
            base_query = base_query.filter(Action.owner == owner)

        total_filtered = base_query.count()

        actions = (
            base_query
            .order_by(Action.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "total_filtered": total_filtered,
            "limit": limit,
            "offset": offset,
            "data": [
                {
                    "action_id": a.action_id,
                    "type": a.type,
                    "description": a.description,
                    "owner": a.owner,
                    "priority": a.priority,
                    "status": a.status,
                    "approval_status": a.approval_status,
                    "sla_status": a.sla_status,
                    "sla_deadline": a.sla_deadline,
                    "created_at": a.created_at,
                    "executed_at": a.executed_at,
                }
                for a in actions
            ],
        }

    finally:
        db.close()


# ---------------------------------------------------------
# GET SINGLE ACTION
# ---------------------------------------------------------
@router.get("/{action_id}")
def get_action_by_id(action_id: str):

    db = SessionLocal()

    try:
        action = db.query(Action).filter(
            Action.action_id == action_id
        ).first()

        if not action:
            raise HTTPException(
                status_code=404,
                detail="Action not found"
            )

        return {
            "action_id": action.action_id,
            "type": action.type,
            "description": action.description,
            "owner": action.owner,
            "priority": action.priority,
            "status": action.status,
            "approval_status": action.approval_status,
            "sla_status": action.sla_status,
            "sla_deadline": action.sla_deadline,
            "created_at": action.created_at,
            "executed_at": action.executed_at,
        }

    finally:
        db.close()