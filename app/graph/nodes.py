import json
from datetime import datetime
from pathlib import Path

from app.agents.ingestion_agent import DataIngestionAgent
from app.agents.monitoring_agent import MonitoringAgent
from app.agents.reasoning_agent import ReasoningAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.action_agent import ActionAgent

from app.services.logger import logger
from app.state import AgentState
from app.db.database import SessionLocal
from app.db.models import Episode
from app.services.path_config import DEBUG_DIR


# ------------------------------------------------------------
# Debug helper
# ------------------------------------------------------------
def _append_node_debug(node_name: str, stage: str, payload: dict):
    debug_file = DEBUG_DIR / "node_state.ndjson"

    record = {
        "node": node_name,
        "stage": stage,
        "payload": payload,
    }

    try:
        with open(debug_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write node debug record: {e}")


# -------------------------------------------------------------------
# Ingestion Node (LOADS FULL DATASET ONCE PER INVOCATION)
# -------------------------------------------------------------------
def ingestion_node(state: AgentState) -> AgentState:
    logger.info(">>> ENTER ingestion_node")

    simulated_date = state.get("simulated_date")

    # --------------------------------------------------
    # If KPIs already injected (simulation mode)
    # --------------------------------------------------
    if state.get("daily_kpis") is not None:
        logger.info("Using precomputed daily KPIs (simulation optimization)")
        daily_kpis = state["daily_kpis"]
    else:
        logger.info("No precomputed KPIs found. Running full ingestion.")
        agent = DataIngestionAgent(data_dir="data")
        daily_kpis = agent.run()
        state["daily_kpis"] = daily_kpis

    # --------------------------------------------------
    # Time-aware slicing
    # --------------------------------------------------
    if simulated_date:
        sim_dt = datetime.strptime(simulated_date, "%Y-%m-%d")

        historical = daily_kpis[daily_kpis["date"] <= sim_dt]
        current_day = daily_kpis[daily_kpis["date"] == sim_dt]

        state["historical_kpis"] = historical
        state["current_day_kpis"] = current_day

        logger.info(
            f"Ingestion slicing | historical_rows={len(historical)} | current_day_rows={len(current_day)}"
        )

        _append_node_debug(
        "ingestion",
        "output",
        {"rows": len(daily_kpis)},
        )

    logger.info("<<< EXIT ingestion_node")
    return state

# -------------------------------------------------------------------
# Monitoring Node (TIME-AWARE)
# -------------------------------------------------------------------
def monitoring_node(state: AgentState) -> AgentState:
    logger.info(">>> ENTER monitoring_node")

    simulated_date = state.get("simulated_date")
    historical_df = state.get("historical_kpis")

    if historical_df is None or historical_df.empty:
        logger.info("No historical data available. Skipping monitoring.")
        state["anomalies"] = []
        return state

    _append_node_debug(
        "monitoring",
        "input",
        {"rows": len(historical_df), "simulated_date": simulated_date},
    )

    agent = MonitoringAgent()

    # IMPORTANT: monitoring must now internally compare
    # last row vs previous rolling window (we will modify MonitoringAgent next)
    result = agent.run(historical_df)

    state["anomalies"] = result.get("anomalies", [])
    state["metrics_df"] = result.get("metrics_df")

    logger.info(
        f"Monitoring detected {len(state['anomalies'])} anomalies for {simulated_date}"
    )

    _append_node_debug(
        "monitoring",
        "output",
        {"anomalies": len(state["anomalies"])},
    )

    logger.info("<<< EXIT monitoring_node")
    return state


# -------------------------------------------------------------------
# Reasoning Node (ONLY IF ANOMALY EXISTS)
# -------------------------------------------------------------------
def reasoning_node(state: AgentState) -> AgentState:
    logger.info(">>> ENTER reasoning_node")

    anomalies = state.get("anomalies", [])
    simulated_date = state.get("simulated_date")

    if not anomalies:
        logger.info(f"No anomalies for {simulated_date}. Skipping reasoning.")
        state["reasoning"] = {}
        state["reasoning_validation"] = {}
        return state

    _append_node_debug("reasoning", "input", {"anomalies": anomalies})

    agent = ReasoningAgent()

    result = agent.run(
        episode={
            "episode_id": f"SIM-{simulated_date}",
            "anomalies": anomalies,
        },
        metrics_df=state.get("metrics_df"),
    )

    state["reasoning"] = result.get("reasoning")
    state["reasoning_validation"] = result.get("validation")

    _append_node_debug(
        "reasoning",
        "output",
        {
            "reasoning": state["reasoning"],
            "validation": state["reasoning_validation"],
        },
    )

    logger.info("<<< EXIT reasoning_node")
    return state


# -------------------------------------------------------------------
# Planning Node
# -------------------------------------------------------------------
def planning_node(state: AgentState) -> AgentState:
    logger.info(">>> ENTER planning_node")

    # --------------------------------------------------
    # Guard: No reasoning available
    # --------------------------------------------------
    if not state.get("reasoning"):
        logger.info("No reasoning available. Skipping planning.")
        state["action_plan"] = {}
        return state

    simulated_date = state.get("simulated_date")

    if not simulated_date:
        logger.warning("planning_node called without simulated_date in state.")
        state["action_plan"] = {}
        return state

    episode_id = f"SIM-{simulated_date}"

    _append_node_debug("planning", "input", state["reasoning"])

    # --------------------------------------------------
    # Run Planner
    # --------------------------------------------------
    agent = PlannerAgent()

    state["action_plan"] = agent.run(
        episode_id=episode_id,
        reasoning=state["reasoning"],
        validation=state.get("reasoning_validation", {}),
    )

    # Persist validation inside action_plan
    state["action_plan"]["validation"] = state.get("reasoning_validation", {})

    # --------------------------------------------------
    # Persist Episode (Simulation-Time Aware)
    # --------------------------------------------------
    db = SessionLocal()
    try:
        existing = db.query(Episode).filter(
            Episode.episode_id == episode_id
        ).first()

        simulated_datetime = datetime.strptime(simulated_date, "%Y-%m-%d")

        if existing:
            logger.info(f"Updating existing episode {episode_id}")

            existing.reasoning = json.dumps(state["reasoning"])
            existing.action_plan = json.dumps(state["action_plan"])
            existing.created_at = simulated_datetime  # keep aligned with simulation

        else:
            logger.info(f"Creating new episode {episode_id}")

            record = Episode(
                episode_id=episode_id,
                reasoning=json.dumps(state["reasoning"]),
                action_plan=json.dumps(state["action_plan"]),
                created_at=simulated_datetime,
            )
            db.add(record)

        db.commit()

    except Exception as e:
        logger.exception(f"Failed to persist episode {episode_id}: {e}")
        db.rollback()
        raise

    finally:
        db.close()

    _append_node_debug("planning", "output", state["action_plan"])

    logger.info("<<< EXIT planning_node")

    return state


# -------------------------------------------------------------------
# Execution Node
# -------------------------------------------------------------------
def execution_node(state: AgentState) -> AgentState:
    logger.info(">>> ENTER execution_node")

    if not state.get("action_plan"):
        logger.info("No action plan generated. Skipping execution.")
        state["execution_result"] = {}
        return state

    _append_node_debug("execution", "input", state["action_plan"])

    agent = ActionAgent()

    state["execution_result"] = agent.run(
        state["action_plan"], 
        simulated_date=state.get("simulated_date")
        )

    _append_node_debug("execution", "output", state["execution_result"])

    logger.info("<<< EXIT execution_node")
    return state