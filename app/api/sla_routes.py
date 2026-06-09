from fastapi import APIRouter
from app.db.database import SessionLocal
from app.db.models import Action

router = APIRouter(
    prefix="/sla",
    tags=["SLA Monitoring"]
)


@router.get("/breached")
def get_breached_actions():
    db = SessionLocal()
    try:
        actions = db.query(Action).filter(
            Action.sla_status == "breached"
        ).all()

        return {
            "count": len(actions),
            "data": [
                {
                    "action_id": a.action_id,
                    "owner": a.owner,
                    "priority": a.priority,
                    "sla_deadline": a.sla_deadline,
                    "status": a.status,
                }
                for a in actions
            ],
        }
    finally:
        db.close()


@router.get("/active")
def get_active_sla_actions():
    db = SessionLocal()
    try:
        actions = db.query(Action).filter(
            Action.sla_status == "active"
        ).all()

        return {
            "count": len(actions),
            "data": [
                {
                    "action_id": a.action_id,
                    "owner": a.owner,
                    "priority": a.priority,
                    "sla_deadline": a.sla_deadline,
                    "status": a.status,
                }
                for a in actions
            ],
        }
    finally:
        db.close()