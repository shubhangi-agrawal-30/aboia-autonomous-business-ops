import requests

BACKEND_URL = "http://localhost:8000"


def check_health():
    try:
        response = requests.get(f"{BACKEND_URL}/v1/system/health")
        return response.status_code == 200
    except Exception:
        return False


def get_system_metrics():
    try:
        response = requests.get(f"{BACKEND_URL}/v1/system/metrics")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def get_episodes():
    try:
        response = requests.get(f"{BACKEND_URL}/v1/episodes/")
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
    except Exception:
        return []


def run_day(date_str, api_key):
    """
    Step-by-step simulation execution for a single day.
    """

    payload = {
        "start_date": date_str,
        "end_date": date_str
    }

    headers = {
        "x-api-key": api_key
    }

    try:
        response = requests.post(
            f"{BACKEND_URL}/v1/run_day",
            json=payload,
            headers=headers
        )

        return response.status_code == 200

    except Exception:
        return False


def get_pending_actions():
    try:
        response = requests.get(f"{BACKEND_URL}/v1/approvals/pending")
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
    except Exception:
        return []


def approve_action(action_id, api_key="dev-secret-key"):
    try:
        headers = {"x-api-key": api_key}
        response = requests.post(f"{BACKEND_URL}/v1/approvals/{action_id}/approve", headers=headers)
        return response.status_code == 200
    except Exception:
        return False


def reject_action(action_id, api_key="dev-secret-key"):
    try:
        headers = {"x-api-key": api_key}
        response = requests.post(f"{BACKEND_URL}/v1/approvals/{action_id}/reject", headers=headers)
        return response.status_code == 200
    except Exception:
        return False

def trigger_execution_loop(api_key="dev-secret-key", simulated_date: str = None):
    try:
        headers = {"x-api-key": api_key}
        params = {}
        if simulated_date:
            params["simulated_date"] = simulated_date
        response = requests.post(f"{BACKEND_URL}/v1/system/run_lifecycle", headers=headers, params=params)
        return response.status_code == 200
    except Exception:
        return False
        
        
def get_kpi_window(end_date: str, metrics: list, window_days: int = 7):
    try:
        params = {
            "end_date": end_date,
            "metrics": metrics,
            "window_days": window_days
        }
        # metrics is a list, requests can handle list in params natively
        response = requests.get(f"{BACKEND_URL}/v1/system/kpi_window", params=params)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception:
        return {}