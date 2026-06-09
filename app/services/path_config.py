from pathlib import Path
BASE_DIR = Path(__file__).resolve().parents[2]
DEBUG_DIR = BASE_DIR / "debug_output"

DEBUG_DIR.mkdir(parents=True, exist_ok=True)