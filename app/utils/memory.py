import json
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def load_past_anomalies():
    file = LOG_DIR / "anomalies.json"
    if file.exists():
        with open(file, "r") as f:
            return json.load(f)
    return []


def save_anomalies(anomalies):
    file = LOG_DIR / "anomalies.json"
    with open(file, "w") as f:
        json.dump(anomalies, f, indent=2)


def is_duplicate_anomaly(current_summary, past_summaries):
    """
    Check if current anomaly pattern was seen before.
    """
    for past in past_summaries:
        if past.get("metrics_affected") == current_summary.get("metrics_affected"):
            return True
    return False