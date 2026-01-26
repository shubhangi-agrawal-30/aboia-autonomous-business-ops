import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


def load_olist_raw_data() -> pd.DataFrame:
    """
    Load and merge Olist orders and order items datasets.
    """
    orders = pd.read_csv(
        RAW_DIR / "olist_orders_dataset.csv",
        parse_dates=["order_purchase_timestamp"],
    )

    items = pd.read_csv(RAW_DIR / "olist_order_items_dataset.csv")

    merged = items.merge(
        orders[["order_id", "order_purchase_timestamp"]],
        on="order_id",
        how="inner",
    )

    merged["date"] = merged["order_purchase_timestamp"].dt.date
    merged["revenue"] = merged["price"]

    return merged


def compute_daily_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate daily KPIs from Olist data.
    Adds synthetic visits and computes conversion rate.
    """

    daily = (
        df.groupby("date")
        .agg(
            orders=("order_id", "nunique"),
            revenue=("revenue", "sum"),
        )
        .reset_index()
    )

    # -----------------------------
    # Create realistic 'visits'
    # -----------------------------
    # Assume conversion rate normally ~3% to 7%
    # visits = orders / conversion_rate
    import numpy as np

    np.random.seed(42)
    conv_rates = np.random.uniform(0.03, 0.07, len(daily))
    daily["visits"] = (daily["orders"] / conv_rates).astype(int)

    # -----------------------------
    # Compute conversion_rate
    # -----------------------------
    daily["conversion_rate"] = daily["orders"] / daily["visits"]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    daily.to_csv(PROCESSED_DIR / "daily_kpis.csv", index=False)

    return daily