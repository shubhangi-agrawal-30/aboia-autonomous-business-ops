from fastapi import APIRouter, HTTPException
from app.db.database import SessionLocal
from app.db.models import Action
from fastapi import Depends
from app.services.auth import verify_api_key
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/approvals",
    tags=["Approvals"]
)

notifier = NotificationService()


# -------------------------------------------
# GET PENDING APPROVALS
# -------------------------------------------
@router.get("/pending")
def get_pending_actions():
    db = SessionLocal()
    try:
        actions = db.query(Action).filter(
            Action.status == "pending_approval"
        ).all()

        return {
            "count": len(actions),
            "data": [
                {
                    "action_id": a.action_id,
                    "description": a.description,
                    "owner": a.owner,
                    "priority": a.priority,
                    "sla_deadline": a.sla_deadline,
                }
                for a in actions
            ],
        }
    finally:
        db.close()


# -------------------------------------------
# APPROVE ACTION
# -------------------------------------------
@router.post("/{action_id}/approve")
def approve_action(action_id: str, api_key: None = Depends(verify_api_key)):
    db = SessionLocal()
    try:
        action = db.query(Action).filter(
            Action.action_id == action_id
        ).first()

        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        if action.status != "pending_approval":
            raise HTTPException(
                status_code=400,
                detail="Action not awaiting approval"
            )

        action.status = "approved"
        action.approval_status = "approved"

        db.commit()

        # 🔥 NEW NOTIFICATION SYSTEM
        notifier.send_event("approved", action)

        return {"message": "Action approved successfully"}

    finally:
        db.close()


# -------------------------------------------
# REJECT ACTION
# -------------------------------------------
@router.post("/{action_id}/reject")
def reject_action(action_id: str, api_key: None = Depends(verify_api_key)):
    db = SessionLocal()
    try:
        action = db.query(Action).filter(
            Action.action_id == action_id
        ).first()

        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        if action.status != "pending_approval":
            raise HTTPException(
                status_code=400,
                detail="Action not awaiting approval"
            )

        action.status = "rejected"
        action.approval_status = "rejected"
        action.sla_status = "resolved"

        db.commit()

        # 🔥 NEW NOTIFICATION SYSTEM
        notifier.send_event("rejected", action)

        return {"message": "Action rejected successfully"}

    finally:
        db.close()