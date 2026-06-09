import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from app.graph.workflow import build_workflow
from app.services.logger import logger
from app.db.database import engine
from app.db.models import Base
from app.agents.action_agent import ActionAgent
from app.agents.ingestion_agent import DataIngestionAgent
from app.api.approval_routes import router as approval_router
from app.api.episode_routes import router as episode_router
from app.api.sla_routes import router as sla_router
from app.api.system_routes import router as system_router
from app.api.action_routes import router as action_router
from app.services.auth import verify_api_key


# -------------------------------------------------------------------
# Environment Initialization
# -------------------------------------------------------------------

load_dotenv()

if not os.getenv("API_KEY"):
    raise RuntimeError("API_KEY is not set. Refusing to start application.")

if not os.getenv("GEMINI_API_KEY"):
    raise RuntimeError("GEMINI_API_KEY not configured in environment.")


# -------------------------------------------------------------------
# FastAPI App Initialization
# -------------------------------------------------------------------

app = FastAPI(
    title="ABOIA - Autonomous Business Operations Intelligence Agent",
    description="Governed anomaly-driven AI system operating in simulated business time."
)

logger.info("Starting ABOIA application...")

Base.metadata.create_all(bind=engine)

API_PREFIX = "/v1"

app.include_router(approval_router, prefix=API_PREFIX)
app.include_router(action_router, prefix=API_PREFIX)
app.include_router(episode_router, prefix=API_PREFIX)
app.include_router(sla_router, prefix=API_PREFIX)
app.include_router(system_router, prefix=API_PREFIX)


# -------------------------------------------------------------------
# Lazy Workflow Initialization
# -------------------------------------------------------------------

_workflow = None


def get_workflow():
    global _workflow
    if _workflow is None:
        logger.info("Initializing LangGraph workflow...")
        _workflow = build_workflow()
    return _workflow


# -------------------------------------------------------------------
# KPI Cache (IMPORTANT)
# -------------------------------------------------------------------

_cached_kpis = None


def get_precomputed_kpis():
    """
    Compute daily KPIs once per server lifecycle.
    Reuse for batch and step-by-step execution.
    """
    global _cached_kpis

    if _cached_kpis is None:
        logger.info("[KPI CACHE] Computing daily KPIs...")
        ingestion_agent = DataIngestionAgent(data_dir="data")
        _cached_kpis = ingestion_agent.run()
        logger.info(f"[KPI CACHE] Ready | rows={len(_cached_kpis)}")
    else:
        logger.info("[KPI CACHE] Reusing cached KPIs")

    return _cached_kpis


# -------------------------------------------------------------------
# Health Check
# -------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "ABOIA Simulation Engine is running"}


# -------------------------------------------------------------------
# Request Model
# -------------------------------------------------------------------

class SimulationRequest(BaseModel):
    start_date: str
    end_date: str


# -------------------------------------------------------------------
# Batch Simulation Mode
# -------------------------------------------------------------------

@app.post("/v1/run_simulation")
def run_simulation(
    request: SimulationRequest,
    api_key: None = Depends(verify_api_key)
):
    try:
        start = datetime.strptime(request.start_date, "%Y-%m-%d")
        end = datetime.strptime(request.end_date, "%Y-%m-%d")

        if start > end:
            raise HTTPException(status_code=400, detail="Invalid date range")

        total_days = (end - start).days + 1

        logger.info(
            f"[SIMULATION] Batch mode | {request.start_date} → {request.end_date} | Days: {total_days}"
        )

        daily_kpis = get_precomputed_kpis()
        workflow = get_workflow()

        current = start
        processed_days = 0

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")

            logger.info(f"[SIMULATION] Processing {date_str}")

            workflow.invoke({
                "mode": "simulation",
                "simulated_date": date_str,
                "daily_kpis": daily_kpis
            })

            ActionAgent().run_lifecycle(simulated_date=date_str)

            processed_days += 1
            current += timedelta(days=1)

        logger.info("[SIMULATION] Batch completed")

        return {"status": "success", "days_processed": processed_days}

    except Exception:
        logger.exception("Batch simulation failed")
        raise HTTPException(status_code=500, detail="Simulation failed")


# -------------------------------------------------------------------
# Step-by-Step Mode (Primary UI Mode)
# -------------------------------------------------------------------

@app.post("/v1/run_day")
def run_day(
    request: SimulationRequest,
    api_key: None = Depends(verify_api_key)
):
    try:
        date_str = request.start_date
        simulated_date = datetime.strptime(date_str, "%Y-%m-%d")

        logger.info(f"[RUN_DAY] Processing {date_str}")

        daily_kpis = get_precomputed_kpis()
        workflow = get_workflow()

        workflow.invoke({
            "mode": "simulation",
            "simulated_date": date_str,
            "daily_kpis": daily_kpis
        })

        ActionAgent().run_lifecycle(simulated_date=date_str)

        logger.info(f"[RUN_DAY] Completed {date_str}")

        return {"status": "success", "processed_date": date_str}

    except Exception:
        logger.exception("run_day failed")
        raise HTTPException(status_code=500, detail="run_day failed")