from langgraph.graph import StateGraph, END

from app.state import AgentState
from app.graph.nodes import (
    ingestion_node,
    monitoring_node,
    reasoning_node,
    planning_node,
    execution_node,
)
from app.services.logger import logger


# ------------------------------------------------------------
# Build Simulation Workflow
# ------------------------------------------------------------
def build_workflow():
    """
    Build a linear, time-aware workflow.

    Execution per simulated day:
        ingestion → monitoring → reasoning → planning → execution → END
    """

    logger.info("Building LangGraph workflow (Simulation Mode)")

    graph = StateGraph(AgentState)

    # ---------------- Nodes ----------------
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("monitoring", monitoring_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("planning", planning_node)
    graph.add_node("execution", execution_node)

    # ---------------- Entry Point ----------------
    graph.set_entry_point("ingestion")

    # ---------------- Linear Flow ----------------
    graph.add_edge("ingestion", "monitoring")
    graph.add_edge("monitoring", "reasoning")
    graph.add_edge("reasoning", "planning")
    graph.add_edge("planning", "execution")
    graph.add_edge("execution", END)

    logger.info("LangGraph workflow compiled successfully (Simulation Mode)")

    return graph.compile()