import logging
import os
from pathlib import Path

# -------------------------------------------------
# Log directory & file
# -------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "system.log"

# -------------------------------------------------
# Log level (default INFO, override via env)
# -------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# -------------------------------------------------
# Logger configuration
# -------------------------------------------------
logger = logging.getLogger("ABOIA")
logger.setLevel(LOG_LEVEL)

# Prevent duplicate handlers (important for FastAPI reloads)
if not logger.handlers:

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # ---- File handler ----
    file_handler = logging.FileHandler(LOG_FILE, mode="w")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(LOG_LEVEL)

    # ---- Console handler ----
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(LOG_LEVEL)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# -------------------------------------------------
# Optional: silence noisy third-party logs, keep access logs
# -------------------------------------------------
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)  # Show POST /run etc.
