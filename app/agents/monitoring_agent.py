import pandas as pd
import numpy as np
from typing import Dict, List


class MonitoringAgent:
    """
    Agent 2: Monitoring & Anomaly Detection Agent

    Responsibilities:
    - Analyze daily KPIs
    - Detect anomalies using statistical methods
    - Output structured anomaly signals for reasoning agent
    """

    def __init__(
        self,
        window_size: int = 7,
        zscore_threshold: float = 2.0,
        pct_change_threshold: float = 0.3,
    ):
        """
        :param window_size: Rolling window size for baseline calculation
        :param zscore_threshold: Threshold beyond which a metric is anomalous
        :param pct_change_threshold: Sudden day-over-day change threshold
        """
        self.window_size = window_size
        self.zscore_threshold = zscore_threshold
        self.pct_change_threshold = pct_change_threshold

    # ------------------------------------------------------------------
    # STEP 1: Compute rolling statistics
    # ------------------------------------------------------------------
    def compute_rolling_stats(
        self, df: pd.DataFrame, metric: str
    ) -> pd.DataFrame:
        """
        Computes rolling mean and std deviation for a metric.
        """
        df = df.copy()

        df[f"{metric}_rolling_mean"] = (
            df[metric].rolling(self.window_size).mean()
        )
        df[f"{metric}_rolling_std"] = (
            df[metric].rolling(self.window_size).std()
        )

        return df

    # ------------------------------------------------------------------
    # STEP 2: Detect anomalies using Z-score
    # ------------------------------------------------------------------
    def detect_zscore_anomalies(
        self, df: pd.DataFrame, metric: str
    ) -> List[Dict]:
        """
        Detects anomalies where Z-score exceeds threshold.
        """
        anomalies = []

        valid_rows = df.dropna(
            subset=[f"{metric}_rolling_mean", f"{metric}_rolling_std"]
        )

        for _, row in valid_rows.iterrows():
            if row[f"{metric}_rolling_std"] == 0:
                continue

            z_score = (
                row[metric] - row[f"{metric}_rolling_mean"]
            ) / row[f"{metric}_rolling_std"]

            if abs(z_score) >= self.zscore_threshold:
                anomalies.append(
                    {
                        "date": row["date"],
                        "metric": metric,
                        "value": row[metric],
                        "z_score": round(z_score, 2),
                        "type": "zscore",
                    }
                )

        return anomalies

    # ------------------------------------------------------------------
    # STEP 3: Detect sudden percentage change anomalies
    # ------------------------------------------------------------------
    def detect_pct_change_anomalies(
        self, df: pd.DataFrame, metric: str
    ) -> List[Dict]:
        """
        Detects anomalies based on sudden day-over-day changes.
        """
        anomalies = []

        pct_change = df[metric].pct_change()

        for idx in range(1, len(df)):
            change = pct_change.iloc[idx]

            if abs(change) >= self.pct_change_threshold:
                anomalies.append(
                    {
                        "date": df.iloc[idx]["date"],
                        "metric": metric,
                        "value": df.iloc[idx][metric],
                        "pct_change": round(change, 2),
                        "type": "pct_change",
                    }
                )

        return anomalies

    # ------------------------------------------------------------------
    # STEP 4: Run monitoring pipeline
    # ------------------------------------------------------------------
    def run(self, df: pd.DataFrame) -> Dict:
        """
        Executes the monitoring pipeline and returns detected anomalies.
        """
        monitored_metrics = ["orders", "revenue", "visits", "conversion_rate"]

        all_anomalies = []

        for metric in monitored_metrics:
            df = self.compute_rolling_stats(df, metric)
            all_anomalies.extend(
                self.detect_zscore_anomalies(df, metric)
            )
            all_anomalies.extend(
                self.detect_pct_change_anomalies(df, metric)
            )

        return {
            "anomalies": all_anomalies,
            "metrics_df": df,
        }