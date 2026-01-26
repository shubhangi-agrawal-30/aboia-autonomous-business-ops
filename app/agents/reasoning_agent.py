# from typing import Dict, List
# import json
# import os


# class ReasoningAgent:
#     """
#     Agent 3: LLM-based Reasoning Agent

#     Responsibilities:
#     - Take anomaly signals
#     - Perform business root-cause analysis
#     - Generate structured reasoning output
#     """

#     def __init__(self, llm_provider: str = "mock"):
#         """
#         llm_provider:
#         - "mock"   → no API calls, safe for testing
#         - "openai" → uses OpenAI API (later)
#         """
#         self.llm_provider = llm_provider

#     # -------------------------------------------------
#     # STEP 1: Build prompt for LLM
#     # -------------------------------------------------
#     def _build_prompt(self, anomalies: List[Dict]) -> str:
#         """
#         Converts anomaly signals into an LLM-friendly prompt.
#         """
#         # Convert non-JSON types (like date) into strings
#         serializable_anomalies = []

#         for anomaly in anomalies:
#             clean = {}

#             for key, value in anomaly.items():
#                 # Convert date to string
#                 if hasattr(value, "isoformat"):
#                     clean[key] = value.isoformat()

#                 # Convert numpy types to native Python types
#                 elif hasattr(value, "item"):
#                     clean[key] = value.item()

#                 else:
#                     clean[key] = value
#             serializable_anomalies.append(clean)

#         anomaly_text = json.dumps(serializable_anomalies, indent=2)

#         prompt = f"""
#                 You are a business operations analyst.

#                 Given the following detected anomalies in daily business metrics:

#                 {anomaly_text}

#                 Your task:
#                 - Identify the most likely root cause(s)
#                 - Explain business impact in simple terms
#                 - Assign a risk level (low / medium / high)

#                 Return your response strictly in JSON with keys:
#                 - root_cause
#                 - business_impact
#                 - risk_level
#                 """

#         return prompt.strip()

#     # -------------------------------------------------
#     # STEP 2: Mock reasoning (NO API COST)
#     # -------------------------------------------------
#     def _mock_reasoning(self, anomalies: List[Dict]) -> Dict:
#         """
#         Deterministic reasoning logic for local testing.
#         """
#         metrics = {a["metric"] for a in anomalies}
#         print(metrics)
#         if "visits" in metrics:
#             root_cause = (
#                 "Sudden drop in visits suggests a traffic acquisition issue "
#                 "such as ad campaign downtime or SEO ranking changes."
#             )
#             risk = "high"
#         elif "conversion_rate" in metrics:
#             root_cause = (
#                 "Change in conversion rate suggests pricing, UX, or checkout issues."
#             )
#             risk = "medium"
#         else:
#             root_cause = "Minor metric fluctuations likely due to normal variance."
#             risk = "low"

#         return {
#             "root_cause": root_cause,
#             "business_impact": (
#                 "If unresolved, this may negatively affect revenue and user growth."
#             ),
#             "risk_level": risk,
#         }

#     # -------------------------------------------------
#     # STEP 3: (Optional) OpenAI reasoning
#     # -------------------------------------------------
#     def _openai_reasoning(self, prompt: str) -> Dict:
#         """
#         Uses OpenAI API for reasoning.
#         """
#         from openai import OpenAI

#         client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.3,
#         )

#         content = response.choices[0].message.content
#         return json.loads(content)

#     # -------------------------------------------------
#     # STEP 4: Public run method
#     # -------------------------------------------------
#     def run(self, anomalies: List[Dict]) -> Dict:
#         """
#         Main execution method.
#         """
#         if not anomalies:
#             return {
#                 "root_cause": "No significant anomalies detected.",
#                 "business_impact": "Business metrics are stable.",
#                 "risk_level": "None",
#             }

#         prompt = self._build_prompt(anomalies)

#         if self.llm_provider == "openai":
#             return self._openai_reasoning(prompt)

#         # Default: mock reasoning
#         return self._mock_reasoning(anomalies)


from app.services.llm_service import LLMService
from app.utils.memory import load_past_anomalies, save_anomalies, is_duplicate_anomaly


class ReasoningAgent:
    def __init__(self, llm_provider="ollama"):
        self.llm_provider = llm_provider

        if llm_provider == "ollama":
            self.llm = LLMService()

    def _summarize_anomalies(self, anomalies: list) -> dict:
        """
        Convert raw anomaly list into a compact summary for LLM reasoning.
        """
        if not anomalies:
            return {}

        from collections import defaultdict

        metrics = defaultdict(list)
        dates = []

        for a in anomalies:
            metrics[a["metric"]].append(a)
            dates.append(str(a["date"]))

        summary = {
            "total_anomalies": len(anomalies),
            "date_range": f"{min(dates)} to {max(dates)}",
            "metrics_affected": list(metrics.keys()),
            "metric_summary": {},
        }

        for metric, items in metrics.items():
            pct_changes = [i.get("pct_change", 0) for i in items]
            zscores = [i.get("zscore", 0) for i in items]

            max_change = max(pct_changes) if pct_changes else 0
            max_zscore = max(zscores) if zscores else 0

            summary["metric_summary"][metric] = {
                "count": len(items),
                "max_pct_change": max_change,
                "max_zscore": max_zscore,
            }

            return summary

    def run(self, anomalies: list) -> dict:
        summary = self._summarize_anomalies(anomalies)

        past = load_past_anomalies()

        # Check for duplicate incident
        if is_duplicate_anomaly(summary, past):
            return {
                "summary": "This anomaly pattern has been observed before. No new alert generated.", 
                "possible_causes": [],
                "risk_level": "low",
        }

        # Save current for future memory
        past.append(summary)
        save_anomalies(past)

        return self.llm.generate_reasoning(summary)