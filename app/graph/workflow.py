from langgraph.graph import StateGraph, END
from app.state import AgentState
from app.graph.nodes import (
    ingestion_node,
    monitoring_node,
    reasoning_node,
    planning_node,
    execution_node,
)


def should_continue(state: AgentState):
    if not state.get("anomalies"):
        return END
    return "reasoning"


def build_workflow():
    graph = StateGraph(AgentState)

    graph.add_node("ingestion", ingestion_node)
    graph.add_node("monitoring", monitoring_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("planning", planning_node)
    graph.add_node("execution", execution_node)

    graph.set_entry_point("ingestion")

    graph.add_edge("ingestion", "monitoring")
    graph.add_conditional_edges(
        "monitoring",
        should_continue,
        {
            "reasoning": "reasoning",
            END: END,
        },
    )
    graph.add_edge("reasoning", "planning")
    graph.add_edge("planning", "execution")
    graph.add_edge("execution", END)

    return graph.compile()