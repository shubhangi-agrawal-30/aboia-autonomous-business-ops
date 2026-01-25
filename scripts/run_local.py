# import sys
# from pathlib import Path

# # Add project root to PYTHONPATH
# ROOT_DIR = Path(__file__).resolve().parents[1]
# sys.path.append(str(ROOT_DIR))

# from app.agents.ingestion_agent import DataIngestionAgent
# from app.agents.monitoring_agent import MonitoringAgent
# from app.agents.reasoning_agent import ReasoningAgent
# from app.agents.planner_agent import PlannerAgent
# from app.agents.action_agent import ActionAgent

# def main():

#     # ---------------------------------------
#     # Step 1: Run Agent 1 (Data Ingestion)
#     # ---------------------------------------    
#     agent = DataIngestionAgent(data_dir="data")
#     daily_kpis_df = agent.run()

#     print("\n=== DAILY KPIs (Agent 1 Output) ===")
#     print(daily_kpis_df.head())

#     # ---------------------------------------
#     # Step 2: Run Agent 2 (Monitoring)
#     # ---------------------------------------
#     monitoring_agent = MonitoringAgent(
#         window_size=3,              # small window for demo
#         zscore_threshold=1.5,       # sensitive detection
#         pct_change_threshold=0.25
#     )

#     monitoring_result = monitoring_agent.run(daily_kpis_df)

#     anomalies = monitoring_result["anomalies"]
#     enriched_df = monitoring_result["metrics_df"]

#     print("\n=== DETECTED ANOMALIES (Agent 2 Output) ===")
#     if not anomalies:
#         print("No anomalies detected.")
#     else:
#         for anomaly in anomalies:
#             print(anomaly)

#     # -------------------------
#     # Step 3: Run Agent 3 (Reasoning)
#     # -------------------------
#     reasoning_agent = ReasoningAgent(llm_provider="mock")
#     reasoning_output = reasoning_agent.run(anomalies)
    
#     print("\n=== AGENT 3 OUTPUT (Reasoning) ===")
#     for k, v in reasoning_output.items():
#         print(f"{k}: {v}")

#     # -------------------------
#     # Step 4: Run Agent 4 (Planning)
#     # -------------------------
#     planner_agent = PlannerAgent()
#     action_plan = planner_agent.run(reasoning_output)

#     print("\n=== AGENT 4 OUTPUT (Action Plan) ===")
#     print(action_plan)

#     # -------------------------
#     # Agent 5: Execution
#     # -------------------------
#     action_agent = ActionAgent()
#     execution_result = action_agent.run(action_plan)

#     print("\n=== AGENT 5 OUTPUT (Execution Result) ===")
#     print(execution_result)


# if __name__ == "__main__":
#     main()


from app.graph.workflow import build_workflow


def main():
    workflow = build_workflow()
    final_state = workflow.invoke({})

    print("\n=== FINAL STATE FROM LANGGRAPH ===")
    for key, value in final_state.items():
        print(f"\n--- {key.upper()} ---")
        print(value)


if __name__ == "__main__":
    main()