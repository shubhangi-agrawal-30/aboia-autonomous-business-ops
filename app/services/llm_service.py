import json
import ollama
import re

def extract_json(text: str) -> dict:
    """
    Extract JSON object from LLM response text.
    """
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    return None

def make_json_serializable(obj):
    """
    Recursively convert pandas/numpy types into JSON serializable types.
    """
    import pandas as pd
    import numpy as np

    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(i) for i in obj]
    elif isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    else:
        return obj

class LLMService:
    def __init__(self, model: str = "llama3"):
        self.model = model

    def generate_reasoning(self, anomaly_summary: dict) -> dict:
        clean_anomalies = make_json_serializable(anomaly_summary)
        prompt = f"""
You are a senior business intelligence analyst.

Given the following KPI anomalies detected in an e-commerce system,
analyze them together and explain the most likely business issue.

Anomaly Summary:
{json.dumps(make_json_serializable(clean_anomalies), indent=2)}

Respond ONLY in this JSON format:

{{
  "summary": "...",
  "possible_causes": ["...", "..."],
  "risk_level": "low | medium | high"
}}
"""

        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response["message"]["content"]

        # Try parsing JSON safely
        parsed = extract_json(content)

        if parsed:
            return parsed

        return {
            "summary": content,
            "possible_causes": [],
            "risk_level": "None",
        }