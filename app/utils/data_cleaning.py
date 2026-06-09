import yaml
import pandas as pd
import numpy as np
from pathlib import Path
from app.services.logger import logger

# -------------------------------------------------------------------
# Project paths
# -------------------------------------------------------------------
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]   # ABOIA/

# -------------------------------------------------------------------
# Load raw Olist datasets
# -------------------------------------------------------------------
def load_olist_tables(data_dir: Path):
    """
    Load core Olist datasets required for KPI computation.
    """

    logger.info(f"Loading raw datasets from {data_dir}")

    orders_path = data_dir / "olist_orders_dataset.csv"
    items_path = data_dir / "olist_order_items_dataset.csv"
    customers_path = data_dir / "olist_customers_dataset.csv"

    for path in [orders_path, items_path, customers_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required raw file not found: {path}")

    orders = pd.read_csv(
        orders_path,
        parse_dates=["order_purchase_timestamp"],
    )
    items = pd.read_csv(items_path)
    customers = pd.read_csv(customers_path)

    logger.info(
        f"Loaded orders={len(orders)}, items={len(items)}, customers={len(customers)}"
    )

    return orders, items, customers


# -------------------------------------------------------------------
# Build clean transactional table
# -------------------------------------------------------------------
def build_clean_merged_table(data_dir: Path):
    """
    Build a clean, denormalized transaction-level table
    combining orders, customers, and order items.
    """

    orders, items, customers = load_olist_tables(data_dir)

    # Join orders with customers
    orders = orders.merge(
        customers[["customer_id", "customer_unique_id"]],
        on="customer_id",
        how="left",
    )

    # Join items with orders
    merged = items.merge(
        orders[
            ["order_id", "order_purchase_timestamp", "customer_unique_id"]
        ],
        on="order_id",
        how="inner",
    )

    merged["date"] = merged["order_purchase_timestamp"].dt.date
    merged["gmv"] = merged["price"] + merged["freight_value"]

    logger.info(f"Merged transaction table rows: {len(merged)}")

    return merged


# -------------------------------------------------------------------
# Load KPI config
# -------------------------------------------------------------------
def load_kpi_config():
    """
    Load KPI aggregation and formula definitions from YAML config.
    """

    config_path = PROJECT_ROOT / "config" / "kpis.yaml"
    logger.info(f"Loading KPI config from {config_path}")

    with open(config_path) as f:
        return yaml.safe_load(f)


# -------------------------------------------------------------------
# Compute daily KPIs
# -------------------------------------------------------------------
def compute_daily_kpis(data_dir: Path):
    """
    Build the final daily KPI table used by the monitoring system.

    Steps:
        1. Merge raw datasets
        2. Aggregate core KPIs per day
        3. Generate synthetic visits with trend + seasonality
        4. Compute derived KPIs
        5. Add calendar features
        6. Remove warmup period
    """
    raw_path = Path(data_dir) / "raw"

    if not raw_path.exists():
        raise FileNotFoundError(f"Raw data directory not found: {raw_path}")

    logger.info(">>> ENTER compute_daily_kpis")

    df = build_clean_merged_table(raw_path)
    config = load_kpi_config()

    # ---------------- KPI aggregation ----------------
    agg_dict = {
        kpi: (rule["column"], rule["agg"])
        for kpi, rule in config["kpis"].items()
    }

    daily = (
        df.groupby("date")
        .agg(**agg_dict)
        .reset_index()
        .sort_values("date")
    )

    logger.info(f"Aggregated daily KPI rows: {len(daily)}")

    # Fill ONLY raw count metrics with 0
    raw_cols = ["orders", "unique_users", "items_sold", "gmv"]
    for col in raw_cols:
        daily[col] = daily[col].fillna(0)

    # ---------------- Synthetic visits ----------------
    np.random.seed(42)

    dates = pd.to_datetime(daily["date"])
    trend = np.linspace(0.8, 1.3, len(daily))

    weekday_pattern = dates.dt.weekday.map({
        0: 1.1, 1: 1.1, 2: 1.15,
        3: 1.2, 4: 1.25,
        5: 0.9, 6: 0.85,
    })

    base = daily["orders"] * 20
    noise = np.random.normal(0, 150, len(daily))

    daily["visits"] = (
        base * trend * weekday_pattern + noise
    ).astype(int).clip(lower=50)

    # ---------------- Derived KPIs ----------------
    for kpi, rule in config["derived_kpis"].items():
        daily[kpi] = daily.eval(rule["formula"])

    # Guard against division by zero
    daily.replace([np.inf, -np.inf], np.nan, inplace=True)

    # ---------------- Feature Engineering ----------------
    daily["date"] = pd.to_datetime(daily["date"])
    daily["day_of_week"] = daily["date"].dt.weekday
    daily["is_weekend"] = daily["day_of_week"].isin([5, 6]).astype(int)
    daily["week_of_year"] = daily["date"].dt.isocalendar().week
    daily["month"] = daily["date"].dt.month

    # ---------------- Date continuity check ----------------
    expected_days = pd.date_range(
        start=daily["date"].min(),
        end=daily["date"].max(),
        freq="D",
    )

    if len(expected_days) != len(daily):
        logger.warning(
            "Date gaps detected in daily KPIs. "
            "Rolling statistics may be slightly affected."
        )

    # ---------------- Warmup removal ----------------
    warmup_days = 30
    if len(daily) <= warmup_days:
        logger.warning(
            f"Daily KPI rows ({len(daily)}) <= warmup_days ({warmup_days}); "
            "skipping warmup trimming"
        )
    else:
        daily = daily.iloc[warmup_days:].reset_index(drop=True)

    logger.info(f"Final daily KPI rows after warmup: {len(daily)}")
    logger.info(f"Final KPI columns: {list(daily.columns)}")
    logger.info("<<< EXIT compute_daily_kpis")

    return daily