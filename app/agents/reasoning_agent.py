import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import pandas as pd

from app.services.llm_service import LLMService
from app.services.reasoning_validator import ReasoningValidator
from app.services.path_config import DEBUG_DIR
from app.services.logger import logger


class ReasoningAgent:
    """
    Agent 3: Structured Business Reasoning Layer

    Responsibilities:
    - Transform anomaly list into structured analytical summary
    - Compute deterministic anomaly confidence score
    - Invoke LLM using structured inputs only
    - Validate LLM output using governance rules
    - Persist debug traces for auditability

    NOTE:
    This agent does NOT re-run anomaly detection.
    It only consumes output from MonitoringAgent.
    """

    def __init__(self):
        import yaml
        self.llm_service = LLMService()
        self.validator = ReasoningValidator()

        # Load dynamic confidence weights from governance config
        config_path = Path(__file__).resolve().parents[2] / "config" / "risk_policy.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                self.weights = config.get("confidence_weights", {
                    "points_per_metric": 15,
                    "max_metric_points": 45,
                    "overlap_bonus": 25,
                    "severity_bonus_high": 20,
                    "severity_bonus_medium": 10,
                })
        except Exception as e:
            logger.warning(f"Failed to load risk_policy.yaml: {e}. Using default hardcoded weights.")
            self.weights = {
                "points_per_metric": 15,
                "max_metric_points": 45,
                "overlap_bonus": 25,
                "severity_bonus_high": 20,
                "severity_bonus_medium": 10,
            }

    # ------------------------------------------------------------------
    # STEP 1: Build deterministic anomaly summary
    # ------------------------------------------------------------------
    def _summarize_anomalies(self, anomalies: list, df: pd.DataFrame) -> dict:
        """
        Convert anomaly list into structured business context.

        Adds:
        - Direction inference (increase/decrease)
        - Baseline comparison (7-day rolling context)
        - Overlap detection
        - Severity estimation
        """

        if not anomalies:
            return {}

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        metric_map = defaultdict(list)
        date_map = defaultdict(set)

        for a in anomalies:
            metric_map[a["metric"]].append(a)
            date_map[str(a["date"])].add(a["metric"])

        summary = {
            "metrics_affected": [],
            "metric_details": {},
            "overlap_dates": {},
            "severity": "low",
        }

        # ----------------------------------------
        # Build per-metric analysis
        # ----------------------------------------
        for metric, items in metric_map.items():
            items = sorted(items, key=lambda x: x["date"])
            anomaly_date = pd.to_datetime(items[0]["date"])

            baseline = df[df["date"] < anomaly_date].tail(7)[metric].mean()
            current_row = df[df["date"] == anomaly_date]

            if current_row.empty:
                continue

            value = current_row.iloc[0][metric]

            if pd.isna(baseline):
                direction = "unknown"
                pct_change = None
            else:
                if value > baseline:
                    direction = "increase"
                elif value < baseline:
                    direction = "decrease"
                else:
                    direction = "stable"

                pct_change = ((value - baseline) / baseline) * 100 if baseline != 0 else None

            summary["metrics_affected"].append(metric)

            summary["metric_details"][metric] = {
                "anomaly_date": str(anomaly_date.date()),
                "value": float(value),
                "baseline_7d_avg": float(baseline) if pd.notna(baseline) else None,
                "direction": direction,
                "pct_change_vs_7d": round(pct_change, 2) if pct_change else None,
            }

        # ----------------------------------------
        # Overlap detection
        # ----------------------------------------
        overlaps = {
            date: list(metrics)
            for date, metrics in date_map.items()
            if len(metrics) > 1
        }

        summary["overlap_dates"] = overlaps

        # ----------------------------------------
        # Severity logic
        # ----------------------------------------
        metric_count = len(summary["metrics_affected"])
        overlap_count = len(overlaps)

        if metric_count >= 3 or overlap_count >= 2:
            severity = "high"
        elif metric_count == 2:
            severity = "medium"
        else:
            severity = "low"

        summary["severity"] = severity

        return summary

    # ------------------------------------------------------------------
    # STEP 2: Deterministic anomaly confidence scoring
    # ------------------------------------------------------------------
    def _calculate_confidence(self, summary: dict) -> int:
        """
        Structural anomaly strength score (0–100).

        Based on:
        - Number of metrics impacted
        - Overlap presence
        - Severity level
        """

        score = 0

        metric_count = len(summary.get("metrics_affected", []))
        overlap_count = len(summary.get("overlap_dates", {}))

        # Dynamically load configuration-driven weights
        points_per_metric = self.weights.get("points_per_metric", 15)
        max_metric_points = self.weights.get("max_metric_points", 45)
        overlap_bonus = self.weights.get("overlap_bonus", 25)
        severity_bonus_high = self.weights.get("severity_bonus_high", 20)
        severity_bonus_medium = self.weights.get("severity_bonus_medium", 10)

        score += min(metric_count * points_per_metric, max_metric_points)

        if overlap_count > 0:
            score += overlap_bonus

        if summary.get("severity") == "high":
            score += severity_bonus_high
        elif summary.get("severity") == "medium":
            score += severity_bonus_medium

        return min(score, 100)

    # ------------------------------------------------------------------
    # Debug helper
    # ------------------------------------------------------------------
    def _append_debug_record(self, record: dict):
        debug_file = DEBUG_DIR / "episode_reasoning.ndjson"

        try:
            with open(debug_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append reasoning debug record: {e}")

    # ------------------------------------------------------------------
    # MAIN ENTRYPOINT
    # ------------------------------------------------------------------
    def run(self, episode: dict, metrics_df: pd.DataFrame) -> dict:
        """
        Execute reasoning for one episode.
        """

        logger.info(">>> ENTER ReasoningAgent.run")

        episode_id = episode["episode_id"]
        anomalies = episode.get("anomalies", [])

        if not anomalies:
            logger.info(f"No anomalies for episode {episode_id}")

            fallback = {
                "root_cause": "No significant anomalies detected.",
                "business_impact": "KPIs remain within expected operating range.",
                "risk_level": "low",
                "anomaly_confidence": 10,
                "reasoning_confidence": 10,
            }

            return {
                "reasoning": fallback,
                "validation": {
                    "is_valid": True,
                    "severity": "none",
                    "issues": [],
                },
            }

        # ----------------------------------------
        # Deterministic summary
        # ----------------------------------------
        summary = self._summarize_anomalies(anomalies, metrics_df)
        anomaly_confidence = self._calculate_confidence(summary)

        logger.info(
            f"Episode {episode_id} | "
            f"metrics={len(summary.get('metrics_affected', []))} | "
            f"severity={summary.get('severity')} | "
            f"confidence={anomaly_confidence}"
        )

        # ----------------------------------------
        # LLM reasoning (analytical enforced)
        # ----------------------------------------
        reasoning_output = self.llm_service.generate_reasoning(
            summary=summary,
            anomaly_confidence=anomaly_confidence,
            require_analytical_output=True,
        )
        
        reasoning_output["metrics_affected"] = summary.get("metrics_affected", [])

        # ----------------------------------------
        # Governance validation
        # ----------------------------------------
        validation_result = self.validator.validate(
            reasoning=reasoning_output,
            summary=summary,
        )

        result = {
            "reasoning": reasoning_output,
            "validation": validation_result,
        }

        # Debug output
        self._append_debug_record({
            "timestamp": datetime.utcnow().isoformat(),
            "episode_id": episode_id,
            "summary": summary,
            "output": result,
        })

        logger.info(f"<<< EXIT ReasoningAgent.run | episode={episode_id}")

        return result