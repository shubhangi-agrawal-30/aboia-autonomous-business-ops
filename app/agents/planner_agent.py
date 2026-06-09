import json
import yaml
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from app.services.path_config import DEBUG_DIR
from app.services.logger import logger


BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config"


class PlannerAgent:
    """
    Agent 4: Governance-Aware Planner

    Responsibilities:
    - Apply risk policy
    - Generate deterministic actions
    - Apply escalation rules
    - React to validation evaluation scores
    - Produce explainable decision_trace
    """

    def __init__(self):
        self.risk_policy = self._load_yaml("risk_policy.yaml")
        self.root_cause_action_map = self._load_yaml("root_cause_action_map.yaml")

    # ---------------------------------------------------------
    # YAML Loader
    # ---------------------------------------------------------
    def _load_yaml(self, filename: str) -> Dict:
        with open(CONFIG_DIR / filename, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # ---------------------------------------------------------
    # Debug logging
    # ---------------------------------------------------------
    def _append_debug_record(self, stage: str, payload: Dict):
        debug_file = DEBUG_DIR / "planner_agent.ndjson"

        record = {
            "stage": stage,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        }

        with open(debug_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    # ---------------------------------------------------------
    # Risk Policy
    # ---------------------------------------------------------
    def _apply_risk_policy(self, risk_level: str) -> Dict:
        return self.risk_policy.get(risk_level.lower(), self.risk_policy["low"])

    def _escalate_priority(self, priority: str) -> str:
        mapping = {"P2": "P1", "P1": "P0", "P0": "P0"}
        return mapping.get(priority, priority)

    # ---------------------------------------------------------
    # Deterministic Action ID Generator
    # ---------------------------------------------------------
    def _generate_action_id(self, episode_id: str, keyword: str) -> str:
        safe_keyword = keyword.replace(" ", "_").lower()
        return f"{episode_id}-{safe_keyword}"

    # ---------------------------------------------------------
    # Deterministic Action Generation
    # ---------------------------------------------------------
    def _generate_actions(self, episode_id: str, reasoning: Dict, policy: Dict) -> List[Dict]:

        actions = []
        root_cause = reasoning.get("root_cause", "").lower()

        for keyword, config in self.root_cause_action_map.items():
            # Support dynamic synonyms configured in YAML (falling back to keyword itself)
            synonyms = config.get("synonyms", [keyword])
            
            # Match if any synonym appears in the LLM's unstructured diagnosis string
            if any(syn.lower() in root_cause for syn in synonyms):
                actions.append({
                    "action_id": self._generate_action_id(episode_id, keyword),
                    "type": config["type"],
                    "description": config["description"],
                    "owner": config["owner"],
                    "priority": policy["priority"],
                    "sla_hours": policy["sla_hours"],
                    "requires_approval": policy["requires_approval"],
                    "approval_role": policy["approval_role"],
                    "status": "pending",
                })

        if not actions:
            actions.append({
                "action_id": self._generate_action_id(episode_id, "monitoring"),
                "type": "monitoring",
                "description": "Monitor metrics for next 48 hours",
                "owner": "Operations Team",
                "priority": policy["priority"],
                "sla_hours": policy["sla_hours"],
                "requires_approval": policy["requires_approval"],
                "approval_role": policy["approval_role"],
                "status": "pending",
            })

        return actions

    # ---------------------------------------------------------
    # Main Planner Entry
    # ---------------------------------------------------------
    def run(self, episode_id: str, reasoning: Dict, validation: Dict) -> Dict:

        logger.info(">>> ENTER PlannerAgent.run")

        anomaly_conf = reasoning.get("anomaly_confidence", 0)
        reasoning_conf = reasoning.get("reasoning_confidence", 0)
        risk_level = reasoning.get("risk_level", "low")
        validation_severity = validation.get("severity", "none")

        evaluation = validation.get("evaluation", {})

        overall_score = evaluation.get("overall_reasoning_score", 100)
        grounding_score = evaluation.get("grounding_score", 100)
        risk_alignment_score = evaluation.get("risk_alignment_score", 100)
        confidence_gap_score = evaluation.get("confidence_gap_score", 100)

        policy = self._apply_risk_policy(risk_level)
        actions = self._generate_actions(episode_id, reasoning, policy)

        # Detect if we had to fall back to the default playbook due to no keyword match
        # (Indicates the LLM output an unrecognized/out-of-playbook root cause narrative)
        has_unrecognized_root_cause = any(action.get("type") == "monitoring" and "Monitor metrics" in action.get("description", "") for action in actions)

        effective_priority = policy["priority"]
        effective_requires_approval = policy["requires_approval"]
        escalation_flags = []

        # =====================================================
        # Dynamic Governance Override Gates (Config-Driven)
        # =====================================================
        gates = self.risk_policy.get("override_gates", {})
        min_overall_score = gates.get("min_overall_reasoning_score", 50)
        min_grounding_score = gates.get("min_metric_grounding_score", 40)
        min_risk_alignment_score = gates.get("min_risk_alignment_score", 60)
        max_confidence_gap = gates.get("max_confidence_gap", 50)

        confidence_gap = abs(anomaly_conf - reasoning_conf)

        if validation_severity == "critical":
            escalation_flags.append("critical_validation_override")
            effective_priority = self._escalate_priority(effective_priority)
            effective_requires_approval = True

        if confidence_gap > max_confidence_gap:
            escalation_flags.append("confidence_gap_override")
            effective_requires_approval = True

        # =====================================================
        # Playbook Safety Escalation Rules
        # =====================================================
        if has_unrecognized_root_cause:
            escalation_flags.append("unrecognized_root_cause_override")
            effective_priority = self._escalate_priority(effective_priority)
            effective_requires_approval = True

        # =====================================================
        # Dynamic Governance Escalation Rules
        # =====================================================
        if overall_score < min_overall_score:
            escalation_flags.append("low_overall_reasoning_score")
            effective_priority = self._escalate_priority(effective_priority)
            effective_requires_approval = True

        if grounding_score < min_grounding_score:
            escalation_flags.append("weak_metric_grounding")
            effective_requires_approval = True

        if risk_alignment_score < min_risk_alignment_score:
            escalation_flags.append("risk_misalignment_detected")
            effective_priority = self._escalate_priority(effective_priority)

        # Deduplicate actions by owner and type
        deduped = {}
        for action in actions:
            key = (action.get("owner"), action.get("type"))
            if key not in deduped:
                deduped[key] = action
            else:
                desc1 = deduped[key].get("description", "").rstrip(".")
                desc2 = action.get("description", "")
                deduped[key]["description"] = f"{desc1} AND {desc2}"
                
        actions = list(deduped.values())

        # Apply final governance decisions
        priority_sla_map = {
            "P0": 4,
            "P1": 8,
            "P2": 24
        }

        for action in actions:
            action["priority"] = effective_priority
            action["requires_approval"] = effective_requires_approval
            action["sla_hours"] = priority_sla_map.get(effective_priority, action.get("sla_hours", 24))
            
            # Clean up hallucinated 'None' roles
            if effective_requires_approval:
                role = str(action.get("approval_role", "")).strip()
                if not role or role.lower() in ["none", "n/a", "null"]:
                    action["approval_role"] = "Business Head"
                else:
                    action["approval_role"] = role

        decision_trace = {
            "episode_id": episode_id,
            "risk_level": risk_level,
            "anomaly_confidence": anomaly_conf,
            "reasoning_confidence": reasoning_conf,
            "validation_severity": validation_severity,
            "confidence_gap": confidence_gap,
            "evaluation_scores": evaluation,
            "escalation_flags": escalation_flags,
        }

        action_plan = {
            "generated_at": datetime.utcnow().isoformat(),
            "episode_id": episode_id,
            "risk_level": risk_level,
            "priority": effective_priority,
            "actions": actions,
            "decision_trace": decision_trace,
        }

        self._append_debug_record("final_action_plan", action_plan)

        logger.info("<<< EXIT PlannerAgent.run")

        return action_plan