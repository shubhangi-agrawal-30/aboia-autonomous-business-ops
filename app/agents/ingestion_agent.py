import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional


class DataIngestionAgent:
    """
    Agent 1: Data Ingestion Agent

    Responsibilities:
    - Load raw e-commerce order data
    - Aggregate daily business KPIs
    - Inject controlled synthetic anomalies
    - Output a clean DataFrame for downstream agents
    """

    def __init__(self, data_dir: str):
        """
        :param data_dir: Base data directory (expects data/raw inside it)
        """
        self.data_dir = Path(data_dir)

    # ------------------------------------------------------------------
    # STEP 1: Load raw data
    # ------------------------------------------------------------------
    def load_raw_data(self) -> pd.DataFrame:
        """
        Loads raw e-commerce order data from CSV.

        Expected file:
        data/raw/ecommerce_orders.csv

        Expected columns:
        - order_date (date or datetime)
        - order_id
        - user_id
        - revenue
        """
        file_path = self.data_dir / "raw" / "ecommerce_orders.csv"

        if not file_path.exists():
            raise FileNotFoundError(
                f"Raw data file not found at {file_path}"
            )

        df = pd.read_csv(file_path, parse_dates=["order_date"])

        return df

    # ------------------------------------------------------------------
    # STEP 2: Aggregate daily KPIs
    # ------------------------------------------------------------------
    def aggregate_daily_kpis(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregates raw order data into daily KPIs.

        Generated KPIs:
        - orders
        - revenue
        - unique_users
        - visits (synthetic)
        - conversion_rate
        """
        # Ensure date-only aggregation
        df["date"] = df["order_date"].dt.date

        daily = (
            df.groupby("date")
            .agg(
                orders=("order_id", "nunique"),
                revenue=("revenue", "sum"),
                unique_users=("user_id", "nunique"),
            )
            .reset_index()
        )

        # Synthetic visits (industry-typical assumption)
        # Visits are higher than orders
        rng = np.random.default_rng(seed=42)
        daily["visits"] = (
            daily["orders"] * rng.integers(6, 10, size=len(daily))
        )

        daily["conversion_rate"] = daily["orders"] / daily["visits"]

        return daily

    # ------------------------------------------------------------------
    # STEP 3: Inject synthetic anomalies
    # ------------------------------------------------------------------
    def inject_synthetic_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Injects controlled synthetic anomalies to simulate real-world issues.

        Anomalies injected:
        - Sudden traffic drops
        - Ad-spend-like traffic fluctuations
        """
        df = df.copy()

        if len(df) < 7:
            # Not enough data to inject meaningful anomalies
            return df

        rng = np.random.default_rng(seed=99)

        # Pick random days for traffic drops
        anomaly_indices = rng.choice(
            df.index, size=min(2, len(df)), replace=False
        )

        # Apply traffic drop
        df.loc[anomaly_indices, "visits"] = (
            df.loc[anomaly_indices, "visits"] * 0.6
        ).astype(int)

        # Recalculate conversion rate
        df["conversion_rate"] = df["orders"] / df["visits"]

        return df

    # ------------------------------------------------------------------
    # STEP 4: Run full ingestion pipeline
    # ------------------------------------------------------------------
    def run(self) -> pd.DataFrame:
        """
        Executes the full ingestion pipeline:
        load → aggregate → inject anomalies
        """
        raw_df = self.load_raw_data()
        daily_kpis = self.aggregate_daily_kpis(raw_df)
        final_df = self.inject_synthetic_anomalies(daily_kpis)

        return final_df
