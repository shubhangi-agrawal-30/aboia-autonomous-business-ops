# Shared memory between agents (LangGraph state)

from typing import TypedDict, List, Dict, Optional
import pandas as pd

class AgentState(TypedDict, total=False):
    """
    Shared state passed between LangGraph nodes.
    """

    # ------------------------------------------------------------
    # Execution Mode
    # ------------------------------------------------------------
    mode: str  # "simulation"

    simulated_date: str  # YYYY-MM-DD for current simulated day

    # ------------------------------------------------------------
    # Ingestion output
    # ------------------------------------------------------------
    daily_kpis: pd.DataFrame  # Full KPI dataset (loaded once)

    # ------------------------------------------------------------
    # Time-aware slices
    # ------------------------------------------------------------
    historical_kpis: pd.DataFrame  # Data <= simulated_date
    current_day_kpis: pd.DataFrame  # Single row for simulated_date

    # ------------------------------------------------------------
    # Monitoring output
    # ------------------------------------------------------------
    anomalies: List[Dict]
    metrics_df: pd.DataFrame

    # ------------------------------------------------------------
    # Reasoning output
    # ------------------------------------------------------------
    reasoning: Dict

    # ------------------------------------------------------------
    # Reasoning validation output
    # ------------------------------------------------------------
    reasoning_validation: Dict

    # ------------------------------------------------------------
    # Planner output
    # ------------------------------------------------------------
    action_plan: Dict

    # ------------------------------------------------------------
    # Execution output
    # ------------------------------------------------------------
    execution_result: Dict