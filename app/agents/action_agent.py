from typing import Dict, List
from datetime import datetime
import uuid


class ActionAgent:
    """
    Agent 5: Action / Execution Agent

    Responsibilities:
    - Execute action plans
    - Simulate alerts and task creation
    - Maintain execution audit trail
    """

    def __init__(self):
        pass

    # -------------------------------------------------
    # STEP 1: Simulate notification
    # -------------------------------------------------
    def _send_notification(self, action: Dict) -> Dict:
        """
        Simulates sending a notification (Slack / Email).
        """
        notification_id = str(uuid.uuid4())

        return {
            "notification_id": notification_id,
            "sent_to": action["owner"],
            "message": action["action"],
            "timestamp": datetime.utcnow().isoformat(),
        }

    # -------------------------------------------------
    # STEP 2: Simulate task creation
    # -------------------------------------------------
    def _create_task(self, action: Dict) -> Dict:
        """
        Simulates task / ticket creation.
        """
        task_id = str(uuid.uuid4())

        return {
            "task_id": task_id,
            "owner": action["owner"],
            "priority": action["priority"],
            "sla_hours": action["sla_hours"],
            "created_at": datetime.utcnow().isoformat(),
        }

    # -------------------------------------------------
    # STEP 3: Execute full action plan
    # -------------------------------------------------
    def run(self, action_plan: Dict) -> Dict:
        """
        Executes all actions in the plan.
        """
        executed_actions = []

        for action in action_plan.get("actions", []):
            notification = self._send_notification(action)
            task = self._create_task(action)

            executed_actions.append({
                "action": action["action"],
                "notification": notification,
                "task": task,
            })

        execution_result = {
            "executed_at": datetime.utcnow().isoformat(),
            "risk_level": action_plan.get("risk_level"),
            "executed_actions": executed_actions,
        }

        return execution_result
