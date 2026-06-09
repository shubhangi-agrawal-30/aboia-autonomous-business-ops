from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.services.logger import logger
from app.db.database import SessionLocal
from app.db.models import Action
from app.services.notification_service import NotificationService


class ActionAgent:

    def __init__(self):
        self.notifier = NotificationService()

    # ---------------------------------------------------------
    # Resolve current time (simulation aware)
    # ---------------------------------------------------------
    def _resolve_now(self, simulated_date: Optional[str]) -> datetime:
        if simulated_date:
            return datetime.strptime(simulated_date, "%Y-%m-%d")
        return datetime.utcnow()

    # ---------------------------------------------------------
    # Execute Action
    # ---------------------------------------------------------
    def _execute_action(self, action_record: Action, db, simulated_now: datetime):

        logger.info(f"Executing action {action_record.action_id}")

        try:
            action_record.status = "completed"
            action_record.executed_at = simulated_now
            if action_record.sla_status != "breached":
                action_record.sla_status = "resolved"

            db.commit()

            self.notifier.send_event("completed", action_record)

        except Exception as e:
            action_record.status = "failed"
            action_record.error_message = str(e)
            if action_record.sla_status != "breached":
                action_record.sla_status = "resolved"

            db.commit()

            self.notifier.send_event("failed", action_record)

    # ---------------------------------------------------------
    # SLA Breach Detection (Simulation Aware)
    # ---------------------------------------------------------
    def _check_sla(self, action_record: Action, db, simulated_now: datetime):

        if action_record.status in ["completed", "rejected", "failed"]:
            return

        if (
            action_record.sla_status == "active"
            and action_record.sla_deadline
            and simulated_now > action_record.sla_deadline
        ):
            action_record.sla_status = "breached"
            db.commit()

            self.notifier.send_event("sla_breached", action_record)

    # ---------------------------------------------------------
    # Main Lifecycle Entry (Action Creation)
    # ---------------------------------------------------------
    def run(self, action_plan: Dict, simulated_date: Optional[str] = None) -> Dict:

        db = SessionLocal()
        results: List[Dict] = []

        simulated_now = self._resolve_now(simulated_date)

        try:
            for action in action_plan.get("actions", []):

                existing = db.query(Action).filter(
                    Action.action_id == action["action_id"]
                ).first()

                # Idempotent behavior (deterministic ID)
                if existing:
                    results.append({
                        "action_id": existing.action_id,
                        "status": existing.status,
                        "approval_status": existing.approval_status,
                        "sla_status": existing.sla_status,
                    })
                    continue

                created_time = simulated_now

                sla_deadline = created_time + timedelta(
                    hours=action.get("sla_hours", 24)
                )

                requires_approval = action.get("requires_approval", False)

                if requires_approval:
                    status = "pending_approval"
                    approval_status = "waiting"
                else:
                    status = "approved"
                    approval_status = "not_required"

                action_record = Action(
                    action_id=action["action_id"],
                    type=action.get("type"),
                    description=action.get("description"),
                    owner=action.get("owner"),
                    priority=action.get("priority"),
                    status=status,
                    approval_status=approval_status,
                    sla_hours=action.get("sla_hours", 24),
                    created_at=created_time,
                    sla_deadline=sla_deadline,
                    sla_status="active",
                )

                db.add(action_record)
                db.commit()
                db.refresh(action_record)

                self.notifier.send_event("created", action_record)

                if requires_approval:
                    self.notifier.send_event("approval_required", action_record)

                    results.append({
                        "action_id": action_record.action_id,
                        "status": action_record.status,
                        "approval_status": action_record.approval_status,
                        "sla_status": action_record.sla_status,
                    })
                    continue

                # Execute immediately
                self._execute_action(action_record, db, simulated_now)

                results.append({
                    "action_id": action_record.action_id,
                    "status": action_record.status,
                    "approval_status": action_record.approval_status,
                    "sla_status": action_record.sla_status,
                })

            return {
                "processed_at": simulated_now.isoformat(),
                "actions": results,
            }

        finally:
            db.close()

    # ---------------------------------------------------------
    # Lifecycle Worker (Simulation Aware)
    # ---------------------------------------------------------
    def run_lifecycle(self, simulated_date: Optional[str] = None) -> Dict:

        logger.info(">>> ENTER ActionAgent.run_lifecycle")

        db = SessionLocal()
        results: List[Dict] = []

        simulated_now = self._resolve_now(simulated_date)

        try:
            # Claim approved actions
            approved_actions = db.query(Action).filter(
                Action.status == "approved"
            ).all()

            for action_record in approved_actions:

                rows_updated = (
                    db.query(Action)
                    .filter(
                        Action.action_id == action_record.action_id,
                        Action.status == "approved"
                    )
                    .update({"status": "in_progress"})
                )

                db.commit()

                if rows_updated == 0:
                    continue

                db.refresh(action_record)

                self._execute_action(action_record, db, simulated_now)

                results.append({
                    "action_id": action_record.action_id,
                    "status": action_record.status,
                    "approval_status": action_record.approval_status,
                    "sla_status": action_record.sla_status,
                })

            # SLA checks
            active_actions = db.query(Action).filter(
                Action.sla_status == "active"
            ).all()

            for action_record in active_actions:
                self._check_sla(action_record, db, simulated_now)

            logger.info("<<< EXIT ActionAgent.run_lifecycle")

            return {
                "processed_at": simulated_now.isoformat(),
                "processed_actions": results,
            }

        finally:
            db.close()