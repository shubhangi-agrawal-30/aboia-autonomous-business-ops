from typing import Dict, List
from datetime import datetime


class PlannerAgent:
    """
    Agent 4: Action Planning Agent

    Responsibilities:
    - Convert reasoning into concrete actions
    - Assign priority and ownership
    - Output a structured action plan
    """

    def __init__(self):
        pass

    # -------------------------------------------------
    # STEP 1: Generate action items
    # -------------------------------------------------
    def _generate_actions(self, reasoning: Dict) -> List[Dict]:
        """
        Maps reasoning output to actionable steps.
        """
        actions = []

        risk = reasoning.get("risk_level", "low")
        root_cause = reasoning.get("root_cause", "").lower()

        if risk == "high":
            priority = "P0"
        elif risk == "medium":
            priority = "P1"
        else:
            priority = "P2"

        if "traffic" in root_cause or "visits" in root_cause:
            actions.append({
                "action": "Investigate traffic sources and ad campaigns",
                "owner": "Marketing Team",
                "priority": priority,
                "sla_hours": 4,
            })

        if "conversion" in root_cause:
            actions.append({
                "action": "Review checkout funnel and recent UI changes",
                "owner": "Product Team",
                "priority": priority,
                "sla_hours": 8,
            })

        if not actions:
            actions.append({
                "action": "Monitor metrics for next 48 hours",
                "owner": "Operations Team",
                "priority": priority,
                "sla_hours": 24,
            })

        return actions

    # -------------------------------------------------
    # STEP 2: Build final action plan
    # -------------------------------------------------
    def run(self, reasoning: Dict) -> Dict:
        """
        Main planning method.
        """
        actions = self._generate_actions(reasoning)

        action_plan = {
            "generated_at": datetime.utcnow().isoformat(),
            "risk_level": reasoning.get("risk_level", "low"),
            "actions": actions,
        }

        return action_plan