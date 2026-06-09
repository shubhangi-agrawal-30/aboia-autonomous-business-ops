import os
from fastapi import Header, HTTPException

API_KEY = os.getenv("API_KEY")

def verify_api_key(x_api_key: str = Header(None)):
    """
    Simple API key verification dependency.
    Assumes API_KEY has already been validated at startup.
    """

    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")