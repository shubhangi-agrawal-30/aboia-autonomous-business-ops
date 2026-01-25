from typing import TypedDict, List, Dict
import pandas as pd


class AgentState(TypedDict, total=False):
    daily_kpis: pd.DataFrame
    anomalies: List[Dict]
    reasoning: Dict
    action_plan: Dict
    execution_result: Dict