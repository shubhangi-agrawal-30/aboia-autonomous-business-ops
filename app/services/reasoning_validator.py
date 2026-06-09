import json
import re
from typing import Dict, List
from datetime import datetime

from app.services.path_config import DEBUG_DIR
from app.services.logger import logger


class ReasoningValidator:
    """
    Enterprise Governance Evaluation Layer for LLM Reasoning.

    Responsibilities:
    - Validate schema correctness
    - Evaluate structural risk alignment
    - Measure anomaly vs reasoning confidence consistency
    - Score metric grounding (nuanced)
    - Score analytical depth using structural signals
    - Produce explainable evaluation metadata
    - NEVER mutate reasoning
    """

    ALLOWED_RISK_LEVELS = {"low", "medium", "high"}

    BUSINESS_SYNONYMS = {
        "visits": ["traffic", "visitors", "sessions"],
        "orders": ["sales", "purchases"],
        "items_sold": ["units", "products sold"],
        "conversion_rate": ["conversion", "checkout", "funnel"],
        "aov": ["average order value", "basket size"],
    }

    def __init__(self):
        self.debug_file = DEBUG_DIR / "reasoning_validation.ndjson"
        self.risk_policy = {}
        try:
            from pathlib import Path
            import yaml
            base_dir = Path(__file__).resolve().parents[2]
            config_path = base_dir / "config" / "risk_policy.yaml"
            with open(config_path, "r", encoding="utf-8") as f:
                self.risk_policy = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load risk_policy.yaml in ReasoningValidator: {e}")

    # ------------------------------------------------------------
    # Debug persistence
    # ------------------------------------------------------------
    def _append_debug_record(self, record: Dict):
        try:
            with open(self.debug_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as e:
            logger.warning(f"ReasoningValidator debug write failed: {e}")

    # ------------------------------------------------------------
    # Utility: check percentage mention
    # ------------------------------------------------------------
    def _contains_percentage(self, text: str) -> bool:
        return bool(re.search(r"\d+(\.\d+)?\s?%", text))

    # ------------------------------------------------------------
    # Main validation entrypoint
    # ------------------------------------------------------------
    def validate(self, reasoning: Dict, summary: Dict) -> Dict:

        logger.info(">>> ENTER ReasoningValidator.validate")

        # Load scoring configuration dynamically with robust defaults
        scoring_config = self.risk_policy.get("validation_scoring", {})
        allowed_risk_levels = set(scoring_config.get("allowed_risk_levels", self.ALLOWED_RISK_LEVELS))
        synonym_grounding_weight = scoring_config.get("synonym_grounding_weight", 0.6)
        min_grounding_alert_score = scoring_config.get("min_grounding_alert_score", 40)
        narrative_depth_min_words = scoring_config.get("narrative_depth_min_words", 12)
        depth_weights = scoring_config.get("depth_weights", {
            "percentage_change": 30,
            "baseline_reference": 25,
            "date_reference": 15,
            "multi_metric_context": 20,
            "narrative_depth": 10
        })

        issues: List[str] = []
        severity = "none"
        explanations = {}

        root_cause = reasoning.get("root_cause", "")
        business_impact = reasoning.get("business_impact", "")
        risk_level = reasoning.get("risk_level")
        anomaly_conf = reasoning.get("anomaly_confidence")
        reasoning_conf = reasoning.get("reasoning_confidence")

        metrics = summary.get("metrics_affected", [])
        episode_severity = summary.get("severity")

        combined_text = f"{root_cause} {business_impact}".lower()

        # =========================================================
        # 1️⃣ Schema Validation
        # =========================================================
        if not root_cause:
            issues.append("Missing root_cause")
            severity = "critical"

        if risk_level not in allowed_risk_levels:
            issues.append(f"Invalid risk_level: {risk_level}")
            severity = "critical"

        if not isinstance(anomaly_conf, int) or not (0 <= anomaly_conf <= 100):
            issues.append("Invalid anomaly_confidence")
            severity = "critical"

        if not isinstance(reasoning_conf, int) or not (0 <= reasoning_conf <= 100):
            issues.append("Invalid reasoning_confidence")
            severity = "critical"

        # =========================================================
        # 2️⃣ Risk Alignment (Nuanced)
        # =========================================================
        risk_alignment_score = 100

        if episode_severity == "high" and risk_level == "low":
            risk_alignment_score = 30
            issues.append("High structural severity but low risk assigned")
            severity = "warning" if severity != "critical" else severity

        elif episode_severity == "high" and risk_level == "medium":
            risk_alignment_score = 70

        elif episode_severity == "medium" and risk_level == "low":
            risk_alignment_score = 60

        if risk_alignment_score == 100:
            explanations["risk_alignment"] = f"Perfect alignment. The generated risk level '{risk_level}' appropriately matches the structural episode severity of '{episode_severity}'."
        else:
            explanations["risk_alignment"] = f"Risk mismatch detected. The generated risk level '{risk_level}' does not fully align with the structural episode severity of '{episode_severity}'."

        # =========================================================
        # 3️⃣ Confidence Gap (Keep Strong)
        # =========================================================
        confidence_gap_score = 100
        gap = abs(anomaly_conf - reasoning_conf)

        confidence_gap_score = max(0, 100 - gap)

        if gap > 60:
            issues.append("Extreme confidence mismatch")
            severity = "critical"

        elif gap > 40:
            issues.append("Large confidence mismatch")
            severity = "warning" if severity != "critical" else severity

        if gap == 0:
            explanations["confidence_gap"] = f"Perfect confidence parity. AI certainty ({reasoning_conf}%) perfectly matches the statistical anomaly strength ({anomaly_conf}%)."
        elif gap <= 40:
            explanations["confidence_gap"] = f"Acceptable confidence variance. AI certainty ({reasoning_conf}%) is reasonably close to the statistical anomaly strength ({anomaly_conf}%)."
        else:
            explanations["confidence_gap"] = f"Significant confidence gap! AI certainty ({reasoning_conf}%) diverges heavily from the statistical anomaly strength ({anomaly_conf}%)."

        # =========================================================
        # 4️⃣ Grounding Score (Nuanced)
        # =========================================================
        grounding_score = 0

        if metrics:
            grounded_points = 0

            for metric in metrics:
                metric_lower = metric.lower()
                clean_metric = metric_lower.replace("_", " ")

                # Explicit mention
                if metric_lower in combined_text or clean_metric in combined_text:
                    grounded_points += 1
                    continue

                # Synonym mention
                synonyms = self.BUSINESS_SYNONYMS.get(metric_lower, [])
                if any(s in combined_text for s in synonyms):
                    grounded_points += synonym_grounding_weight
                    continue

            grounding_ratio = grounded_points / len(metrics)
            grounding_score = int(min(grounding_ratio, 1.0) * 100)

            if grounding_score < min_grounding_alert_score:
                issues.append("Root cause weakly grounded in affected metrics")
                severity = "warning" if severity != "critical" else severity

        if grounding_score == 100:
            explanations["grounding"] = f"Excellent metric grounding. The reasoning explicitly references the affected database metrics: {metrics}."
        elif grounding_score >= min_grounding_alert_score:
            explanations["grounding"] = f"Partial metric grounding. The reasoning indirectly references or misses some affected metrics: {metrics}."
        else:
            explanations["grounding"] = f"Poor metric grounding! The reasoning failed to properly reference the affected metrics: {metrics}."

        # =========================================================
        # 5️⃣ Analytical Depth (Signal-Based)
        # =========================================================
        analytical_depth_score = 0
        depth_signals = []

        # % change
        if self._contains_percentage(combined_text):
            analytical_depth_score += depth_weights.get("percentage_change", 30)
            depth_signals.append("percentage_change")

        # Baseline reference
        if "baseline" in combined_text or "average" in combined_text:
            analytical_depth_score += depth_weights.get("baseline_reference", 25)
            depth_signals.append("baseline_reference")

        # Date reference
        anomaly_dates = [details.get("anomaly_date") for details in summary.get("metric_details", {}).values() if "anomaly_date" in details]
        if any(d in combined_text for d in anomaly_dates if d):
            analytical_depth_score += depth_weights.get("date_reference", 15)
            depth_signals.append("date_reference")

        # Multi-metric reasoning
        if len(metrics) > 1:
            analytical_depth_score += depth_weights.get("multi_metric_context", 20)
            depth_signals.append("multi_metric_context")

        # Minimum narrative length
        if len(root_cause.split()) > narrative_depth_min_words:
            analytical_depth_score += depth_weights.get("narrative_depth", 10)
            depth_signals.append("narrative_depth")

        analytical_depth_score = min(analytical_depth_score, 100)

        if analytical_depth_score >= 80:
            explanations["analytical_depth"] = f"High analytical depth achieved. Detected advanced reasoning signals: {', '.join(depth_signals)}."
        elif analytical_depth_score >= 40:
            explanations["analytical_depth"] = f"Moderate analytical depth. Detected some reasoning signals: {', '.join(depth_signals) if depth_signals else 'None'}."
        else:
            explanations["analytical_depth"] = f"Low analytical depth. The reasoning is overly simplistic. Detected signals: {', '.join(depth_signals) if depth_signals else 'None'}."

        # =========================================================
        # 6️⃣ Overall Score (Balanced Average)
        # =========================================================
        overall_reasoning_score = int(
            (
                confidence_gap_score
                + grounding_score
                + risk_alignment_score
                + analytical_depth_score
            ) / 4
        )

        # =========================================================
        # Final Status
        # =========================================================
        is_valid = severity != "critical"

        validation_result = {
            "is_valid": is_valid,
            "severity": severity,
            "issues": issues,
            "evaluation": {
                "confidence_gap_score": confidence_gap_score,
                "grounding_score": grounding_score,
                "risk_alignment_score": risk_alignment_score,
                "analytical_depth_score": analytical_depth_score,
                "overall_reasoning_score": overall_reasoning_score,
                "explanations": explanations,
            },
        }

        self._append_debug_record({
            "timestamp": datetime.utcnow().isoformat(),
            "reasoning": reasoning,
            "validation": validation_result,
        })

        logger.info(
            f"<<< EXIT ReasoningValidator.validate | "
            f"severity={severity} | overall_score={overall_reasoning_score}"
        )

        return validation_result