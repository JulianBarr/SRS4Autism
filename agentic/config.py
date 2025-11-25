from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
AGENT_DATA_DIR = DATA_DIR / "agent"
AGENT_DATA_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_FILE = AGENT_DATA_DIR / "memory.json"

PRINCIPLES_DIR = DATA_DIR / "principles"
PRINCIPLES_DIR.mkdir(parents=True, exist_ok=True)
PRINCIPLES_FILE = PRINCIPLES_DIR / "principles.yaml"

