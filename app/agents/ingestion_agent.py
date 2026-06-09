import pandas as pd
from pathlib import Path

from app.utils.data_cleaning import compute_daily_kpis
from app.utils.validator import validate_daily_kpis
from app.services.path_config import DEBUG_DIR
from app.services.logger import logger


class DataIngestionAgent:
    """
    Agent 1: Data Ingestion Agent

    Responsibilities:
    - Load raw e-commerce data
    - Aggregate daily business KPIs
    - Validate KPI schema and values
    - Persist debug output
    - Output clean DataFrame for downstream agents
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)

    def run(self) -> pd.DataFrame:
        """
        Execute ingestion and KPI aggregation.
        """

        logger.info(">>> ENTER DataIngestionAgent.run")

        # ------------------------------------------------------------
        # Validate input directory
        # ------------------------------------------------------------
        if not self.data_dir.exists():
            logger.error(f"Data directory does not exist: {self.data_dir}")
            raise FileNotFoundError(f"Invalid data_dir: {self.data_dir}")

        logger.info(f"Using data directory: {self.data_dir.resolve()}")

        # ------------------------------------------------------------
        # Compute daily KPIs
        # ------------------------------------------------------------
        try:
            logger.info("Computing daily KPIs from raw data")
            daily = compute_daily_kpis(self.data_dir)
        except Exception as e:
            logger.exception("Failed while computing daily KPIs")
            raise RuntimeError("Ingestion failed during KPI computation") from e

        if daily is None or daily.empty:
            logger.error("Daily KPI DataFrame is empty after computation")
            raise ValueError("Ingestion failed: daily KPIs are empty")

        logger.info(
            f"KPI table generated | rows={len(daily)} | columns={len(daily.columns)}"
        )

        # ------------------------------------------------------------
        # Validate KPI schema and values
        # ------------------------------------------------------------
        try:
            daily = validate_daily_kpis(daily)
        except Exception as e:
            logger.exception("KPI validation failed")
            raise RuntimeError("Ingestion failed during KPI validation") from e

        logger.info("KPI validation successful")

        # ------------------------------------------------------------
        # Log basic KPI metadata (very useful later)
        # ------------------------------------------------------------
        if "date" in daily.columns:
            logger.info(
                f"KPI date range | start={daily['date'].min()} | end={daily['date'].max()}"
            )

        # ------------------------------------------------------------
        # Persist debug output
        # ------------------------------------------------------------
        debug_file = DEBUG_DIR / "daily_kpis.csv"
        daily.to_csv(debug_file, index=False)

        logger.info(f"Debug KPI output written to {debug_file.resolve()}")

        logger.info("<<< EXIT DataIngestionAgent.run")

        return daily