from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from app.db.database import SessionLocal
from app.db.models import Episode, Action
from app.agents.action_agent import ActionAgent
from app.services.auth import verify_api_key
from app.services.logger import logger
from app.agents.ingestion_agent import DataIngestionAgent
import pandas as pd


router = APIRouter(prefix="/system", tags=["System"])


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------
@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ABOIA",
        "message": "System operational"
    }


# --------------------------------------------------
# METRICS / OBSERVABILITY
# --------------------------------------------------
@router.get("/metrics")
def system_metrics():
    db = SessionLocal()

    try:
        total_episodes = db.query(Episode).count()
        total_actions = db.query(Action).count()

        pending_approvals = db.query(Action).filter(
            Action.status == "pending_approval"
        ).count()

        sla_breaches = db.query(Action).filter(
            Action.sla_status == "breached"
        ).count()

        completed_actions = db.query(Action).filter(
            Action.status == "completed"
        ).count()

        failed_actions = db.query(Action).filter(
            Action.status == "failed"
        ).count()

        return {
            "total_episodes": total_episodes,
            "total_actions": total_actions,
            "pending_approvals": pending_approvals,
            "sla_breaches": sla_breaches,
            "completed_actions": completed_actions,
            "failed_actions": failed_actions,
        }

    finally:
        db.close()


# --------------------------------------------------
# KPI WINDOW (Streamlit Graphing)
# --------------------------------------------------
@router.get("/kpi_window")
def get_kpi_window(
    end_date: str = Query(..., description="The date the anomaly occurred"),
    metrics: list[str] = Query(..., description="List of metrics to fetch"),
    window_days: int = Query(7, description="Size of the trailing window")
):
    try:
        from app.services.path_config import DEBUG_DIR
        df_path = DEBUG_DIR / "daily_kpis.csv"
        if not df_path.exists():
            return {}
            
        df = pd.read_csv(df_path)
        df['date'] = pd.to_datetime(df['date'])
        end_dt = pd.to_datetime(end_date)
        start_dt = end_dt - pd.Timedelta(days=window_days - 1)
        
        mask = (df['date'] >= start_dt) & (df['date'] <= end_dt)
        window_df = df[mask].copy()
        
        result = {'dates': window_df['date'].dt.strftime('%Y-%m-%d').tolist()}
        for m in metrics:
            if m in window_df.columns:
                result[m] = window_df[m].tolist()
                
        return result
    except Exception as e:
        logger.error(f"KPI Window fetch failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch KPI Window")


# --------------------------------------------------
# LIFECYCLE WORKER (Simulation Aware)
# --------------------------------------------------
@router.post("/run_lifecycle")
def run_lifecycle(
    simulated_date: Optional[str] = Query(
        None,
        description="Simulated date in YYYY-MM-DD format (optional)"
    ),
    api_key: None = Depends(verify_api_key)
):

    logger.info(">>> ENTER /system/run_lifecycle")

    try:
        agent = ActionAgent()

        result = agent.run_lifecycle(simulated_date=simulated_date)

        logger.info("<<< EXIT /system/run_lifecycle (success)")

        return result

    except Exception as e:
        logger.error(f"/system/run_lifecycle failed: {str(e)}")

        raise HTTPException(
            status_code=500,
            detail="Lifecycle execution failed"
        )