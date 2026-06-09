import pandas as pd
from app.services.logger import logger


def validate_daily_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate the daily KPI dataframe before it goes to MonitoringAgent.

    This function enforces hard invariants required for
    anomaly detection and episode reasoning.
    """

    logger.info(">>> ENTER validate_daily_kpis")

    if df is None or df.empty:
        raise ValueError("Daily KPI DataFrame is empty")

    logger.info(
        f"Validating daily KPIs | rows={len(df)} | cols={len(df.columns)}"
    )

    # ------------------------------------------------------------
    # Required columns
    # ------------------------------------------------------------
    required_cols = [
        "date",
        "orders",
        "unique_users",
        "gmv",
        "visits",
        "conversion_rate",
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
        if df[col].isnull().any():
            null_count = df[col].isnull().sum()
            if col == "date":
                raise ValueError(f"Null values found in 'date' ({null_count} rows) - cannot impute chronological timeline.")
            
            logger.warning(
                f"[INGESTION IMPUTATION] Null values found in '{col}' ({null_count} rows). "
                f"Gracefully patching telemetry gap using linear interpolation..."
            )
            # Gracefully fill gaps using linear interpolation (with forward/backward fill fallbacks)
            df[col] = df[col].interpolate(method="linear").ffill().bfill()


    # ------------------------------------------------------------
    # Date validation
    # ------------------------------------------------------------
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        raise ValueError("'date' column is not datetime type")

    if not df["date"].is_monotonic_increasing:
        raise ValueError("Dates are not sorted in increasing order")

    if df["date"].duplicated().any():
        raise ValueError("Duplicate dates detected in daily KPIs")

    logger.info(
        f"Date range: {df['date'].min().date()} -> {df['date'].max().date()}"
    )

    # ------------------------------------------------------------
    # Numeric validation
    # ------------------------------------------------------------
    numeric_cols = [
        "orders",
        "unique_users",
        "gmv",
        "visits",
        "conversion_rate",
    ]

    for col in numeric_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f"Column '{col}' is not numeric")

    # ------------------------------------------------------------
    # Value constraints
    # ------------------------------------------------------------
    if (df["orders"] < 0).any():
        count = (df["orders"] < 0).sum()
        raise ValueError(f"Negative orders detected ({count} rows)")

    if (df["visits"] < 0).any():
        count = (df["visits"] < 0).sum()
        raise ValueError(f"Negative visits detected ({count} rows)")

    if (df["orders"] > df["visits"]).any():
        count = (df["orders"] > df["visits"]).sum()
        raise ValueError(f"Orders greater than visits detected ({count} rows)")

    if not ((df["conversion_rate"] >= 0) & (df["conversion_rate"] <= 1)).all():
        bad = (~((df["conversion_rate"] >= 0) & (df["conversion_rate"] <= 1))).sum()
        raise ValueError(f"Invalid conversion_rate values ({bad} rows)")

    logger.info("Daily KPI validation passed successfully")
    logger.info("<<< EXIT validate_daily_kpis")

    return df