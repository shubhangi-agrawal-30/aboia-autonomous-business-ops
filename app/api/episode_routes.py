from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import Episode, Action
from app.services.logger import logger
import json

router = APIRouter(prefix="/episodes", tags=["Episodes"])


@router.get("/")
def get_episodes(
    episode_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Retrieve stored anomaly episodes with filtering and pagination.

    Response schema normalized for frontend usage.
    """

    db = SessionLocal()

    try:

        base_query = db.query(Episode)

        if episode_id:
            base_query = base_query.filter(Episode.episode_id == episode_id)

        if start_date:
            base_query = base_query.filter(Episode.created_at >= start_date)

        if end_date:
            base_query = base_query.filter(Episode.created_at <= end_date)

        total_filtered = base_query.count()

        episodes = (
            base_query
            .order_by(Episode.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        data = []

        for ep in episodes:

            # ------------------------
            # Parse reasoning JSON
            # ------------------------

            try:
                reasoning = json.loads(ep.reasoning) if ep.reasoning else {}
            except Exception as err:
                logger.warning(f"Invalid reasoning JSON for {ep.episode_id}: {err}")
                reasoning = {}

            # ------------------------
            # Parse action plan JSON
            # ------------------------

            try:
                action_plan = json.loads(ep.action_plan) if ep.action_plan else {}
            except Exception as err:
                logger.warning(f"Invalid action plan JSON for {ep.episode_id}: {err}")
                action_plan = {}

            decision_trace = action_plan.get("decision_trace", {})

            validation = {"severity": decision_trace.get("validation_severity", "none")}

            evaluation = decision_trace.get("evaluation_scores", {})

            actions_list = action_plan.get("actions", [])
            action_ids = [a.get("action_id") for a in actions_list]
            
            db_actions = db.query(Action).filter(Action.action_id.in_(action_ids)).all() if action_ids else []
            db_actions_map = {a.action_id: a for a in db_actions}
            
            actions = []
            for a in actions_list:
                db_action = db_actions_map.get(a.get("action_id"))
                if db_action:
                    actions.append({
                        "action_id": db_action.action_id,
                        "type": db_action.type,
                        "description": db_action.description,
                        "owner": db_action.owner,
                        "priority": db_action.priority,
                        "status": db_action.status,
                        "approval_status": db_action.approval_status,
                        "approval_role": a.get("approval_role"),
                        "sla_hours": db_action.sla_hours,
                        "sla_status": db_action.sla_status,
                        "created_at": db_action.created_at,
                        "executed_at": db_action.executed_at,
                        "error_message": db_action.error_message,
                    })
                else:
                    actions.append(a)

            data.append({
                "episode_id": ep.episode_id,
                "reasoning": reasoning,
                "actions": actions,
                "validation": validation,
                "evaluation": evaluation,
                "risk_level": reasoning.get("risk_level"),
                "priority": action_plan.get("priority"),
                "created_at": ep.created_at,
            })

        return {
            "total_filtered": total_filtered,
            "limit": limit,
            "offset": offset,
            "data": data,
        }

    finally:
        db.close()