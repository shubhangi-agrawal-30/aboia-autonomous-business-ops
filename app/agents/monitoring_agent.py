import yaml
import json
from pathlib import Path
import pandas as pd
from typing import Dict, List
from collections import Counter

from app.services.path_config import DEBUG_DIR
from app.services.logger import logger

 
# ------------------------------------------------------------
# Config loader
# ------------------------------------------------------------
def load_monitoring_config():
    """
    Load monitoring configuration from YAML.
    """
    config_path = Path(__file__).resolve().parents[2] / "config" / "monitoring.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


class MonitoringAgent:
    """
    Agent 2: Monitoring & Anomaly Detection Agent

    Responsibilities:
    - Analyze daily KPIs
    - Detect anomalies using multiple statistical techniques
    - Return anomalies ONLY for the latest date (simulation-safe)
    """

    def __init__(self):
        config = load_monitoring_config()
        self.monitored_metrics = config["metrics"]
        self.window_size = 7

    # ------------------------------------------------------------
    # Utility helper
    # ------------------------------------------------------------
    def build_anomaly(self, date, metric, value, anomaly_type, score=None):
        return {
            "date": str(date),
            "metric": metric,
            "value": float(value),
            "type": anomaly_type,
            "score": float(score) if score is not None else None,
        }

    # ------------------------------------------------------------
    # Rolling statistics
    # ------------------------------------------------------------
    def compute_rolling_stats(self, df: pd.DataFrame, metric: str) -> pd.DataFrame:
        df = df.copy()
        df[f"{metric}_rolling_mean"] = df[metric].rolling(self.window_size).mean()
        df[f"{metric}_rolling_std"] = df[metric].rolling(self.window_size).std()
        return df

    # ------------------------------------------------------------
    # Auto-tuned thresholds
    # ------------------------------------------------------------
    def auto_tune_zscore(self, df: pd.DataFrame, metric: str) -> float:
        rolling_mean = df[metric].rolling(self.window_size).mean()
        rolling_std = df[metric].rolling(self.window_size).std()
        zscores = ((df[metric] - rolling_mean) / rolling_std).dropna().abs()
        return max(zscores.quantile(0.95), 0.8)

    def auto_tune_pct_threshold(self, df: pd.DataFrame, metric: str) -> float:
        pct_changes = df[metric].pct_change().dropna().abs()
        return max(pct_changes.quantile(0.95), 0.2)

    # ------------------------------------------------------------
    # Detection methods 
    # ------------------------------------------------------------
    def detect_zscore_anomalies(self, df, metric, threshold):
        anomalies = []
        valid_rows = df.dropna(subset=[f"{metric}_rolling_mean", f"{metric}_rolling_std"])

        for _, row in valid_rows.iterrows():
            std = row[f"{metric}_rolling_std"]
            if std == 0:
                continue

            z_score = (row[metric] - row[f"{metric}_rolling_mean"]) / std
            if abs(z_score) >= threshold:
                anomalies.append(
                    self.build_anomaly(row["date"], metric, row[metric], "zscore", z_score)
                )
        return anomalies

    def detect_pct_change_anomalies(self, df, metric, threshold):
        anomalies = []
        pct_change = df[metric].pct_change()

        for idx in range(1, len(df)):
            change = pct_change.iloc[idx]
            if abs(change) >= threshold:
                anomalies.append(
                    self.build_anomaly(
                        df.iloc[idx]["date"],
                        metric,
                        df.iloc[idx][metric],
                        "pct_change",
                        change,
                    )
                )
        return anomalies

    def detect_iqr_anomalies(self, df, metric):
        anomalies = []
        q1, q3 = df[metric].quantile([0.25, 0.75])
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr

        for _, row in df.iterrows():
            if row[metric] < lower or row[metric] > upper:
                score = min(abs(row[metric] - lower), abs(row[metric] - upper))
                anomalies.append(
                    self.build_anomaly(row["date"], metric, row[metric], "iqr", score)
                )
        return anomalies

    def detect_ewma_anomalies(self, df, metric):
        anomalies = []
        ewma = df[metric].ewm(span=self.window_size).mean()
        local_std = df[metric].rolling(self.window_size).std()

        for idx in range(len(df)):
            if pd.isna(local_std.iloc[idx]):
                continue
            score = abs(df.iloc[idx][metric] - ewma.iloc[idx])
            if score > 2 * local_std.iloc[idx]:
                anomalies.append(
                    self.build_anomaly(
                        df.iloc[idx]["date"], metric, df.iloc[idx][metric], "ewma", score
                    )
                )
        return anomalies

    def detect_seasonal_anomalies(self, df, metric):
        anomalies = []
        if "day_of_week" not in df.columns:
            return anomalies

        grouped = df.groupby("day_of_week")[metric]
        weekday_mean = grouped.transform("mean")
        weekday_std = grouped.transform("std")

        for idx in range(len(df)):
            std = weekday_std.iloc[idx]
            if pd.isna(std) or std == 0:
                continue
            score = abs(df.iloc[idx][metric] - weekday_mean.iloc[idx])
            if score > 2 * std:
                anomalies.append(
                    self.build_anomaly(
                        df.iloc[idx]["date"], metric, df.iloc[idx][metric], "seasonal", score
                    )
                )
        return anomalies

    def detect_correlation_anomalies(self, df):
        anomalies = []
        for idx in range(1, len(df)):
            prev, row = df.iloc[idx - 1], df.iloc[idx]
            
            # Rule 1: Tracking Script Breakdown (Visits vs Orders -> Conversion Rate)
            if row["visits"] < prev["visits"] * 0.7 and abs(row["orders"] - prev["orders"]) < 5:
                anomalies.append(
                    self.build_anomaly(
                        row["date"],
                        "conversion_rate",
                        row["conversion_rate"],
                        "correlation",
                        prev["visits"] - row["visits"],
                    )
                )

            # Rule 2: Pricing / Revenue Mismatch (Items Sold vs GMV)
            if row["items_sold"] >= prev["items_sold"] * 0.95 and row["gmv"] < prev["gmv"] * 0.7:
                anomalies.append(
                    self.build_anomaly(
                        row["date"],
                        "gmv",
                        row["gmv"],
                        "correlation",
                        prev["gmv"] - row["gmv"],
                    )
                )

            # Rule 3: Bulk Purchase / Bot Activity (Orders vs Unique Users -> Orders per User)
            if row["orders"] > prev["orders"] * 1.4 and row["unique_users"] <= prev["unique_users"] * 1.05:
                anomalies.append(
                    self.build_anomaly(
                        row["date"],
                        "orders_per_user",
                        row["orders_per_user"],
                        "correlation",
                        row["orders"] - prev["orders"],
                    )
                )
        return anomalies

    def deduplicate_anomalies(self, anomalies: List[Dict]) -> List[Dict]:
        seen = {}
        for a in anomalies:
            key = (a["date"], a["metric"])
            if key not in seen:
                seen[key] = a
            else:
                seen[key]["type"] += f", {a['type']}"
        return list(seen.values())

    # ------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------
    def run(self, df: pd.DataFrame) -> Dict:

        logger.info(">>> ENTER MonitoringAgent.run (Time-Aware Mode)")

        if df.empty:
            logger.warning("MonitoringAgent received empty dataframe")
            return {"anomalies": [], "metrics_df": df}

        self.window_size = max(7, int(len(df) * 0.01))
        logger.info(f"Monitoring window size set to {self.window_size}")

        df = df.sort_values("date").reset_index(drop=True)

        simulated_date = df.iloc[-1]["date"]
        logger.info(f"Simulated evaluation date: {simulated_date}")

        all_anomalies: List[Dict] = []

        for metric in self.monitored_metrics:
            logger.info(f"Detecting anomalies for metric: {metric}")

            df = self.compute_rolling_stats(df, metric)

            z_th = self.auto_tune_zscore(df, metric)
            p_th = self.auto_tune_pct_threshold(df, metric)

            all_anomalies.extend(self.detect_zscore_anomalies(df, metric, z_th))
            all_anomalies.extend(self.detect_pct_change_anomalies(df, metric, p_th))
            all_anomalies.extend(self.detect_iqr_anomalies(df, metric))
            all_anomalies.extend(self.detect_ewma_anomalies(df, metric))
            all_anomalies.extend(self.detect_seasonal_anomalies(df, metric))

        all_anomalies.extend(self.detect_correlation_anomalies(df))

        logger.info(f"Raw anomalies detected (all dates): {len(all_anomalies)}")

        # Deduplicate first
        all_anomalies = self.deduplicate_anomalies(all_anomalies)

        # --------------------------------------------------------
        # TIME-AWARE FILTERING: only return anomalies
        # for the simulated_date (last row)
        # --------------------------------------------------------
        filtered_anomalies = [
            a for a in all_anomalies
            if str(a["date"]) == str(simulated_date)
        ]

        logger.info(
            f"Anomalies for simulated date {simulated_date}: "
            f"{len(filtered_anomalies)}"
        )

        # Debug full anomaly list
        with open(DEBUG_DIR / "anomalies_full.json", "w") as f:
            json.dump(all_anomalies, f, indent=2)

        # Debug current day anomalies
        with open(DEBUG_DIR / "anomalies_current_day.json", "w") as f:
            json.dump(filtered_anomalies, f, indent=2)

        logger.info("<<< EXIT MonitoringAgent.run")

        return {
            "anomalies": filtered_anomalies,
            "metrics_df": df,
        }
