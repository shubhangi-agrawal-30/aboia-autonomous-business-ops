from app.agents.ingestion_agent import DataIngestionAgent
from app.agents.monitoring_agent import MonitoringAgent
from app.agents.reasoning_agent import ReasoningAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.action_agent import ActionAgent
from app.state import AgentState


def ingestion_node(state: AgentState) -> AgentState:
    agent = DataIngestionAgent(data_dir="data")
    state["daily_kpis"] = agent.run()
    return state


def monitoring_node(state: AgentState) -> AgentState:
    agent = MonitoringAgent(
        window_size=3,
        zscore_threshold=1.5,
        pct_change_threshold=0.25,
    )
    result = agent.run(state["daily_kpis"])
    state["anomalies"] = result["anomalies"]
    return state


def reasoning_node(state: AgentState) -> AgentState:
    agent = ReasoningAgent(llm_provider="mock")
    state["reasoning"] = agent.run(state["anomalies"])
    return state


def planning_node(state: AgentState) -> AgentState:
    agent = PlannerAgent()
    state["action_plan"] = agent.run(state["reasoning"])
    return state


def execution_node(state: AgentState) -> AgentState:
    agent = ActionAgent()
    state["execution_result"] = agent.run(state["action_plan"])
    return state