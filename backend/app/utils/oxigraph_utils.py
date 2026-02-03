import pyoxigraph as oxigraph
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Robust Project Root Detection
# File is at: SRS4Autism/backend/utils/oxigraph_utils.py
# Go up 3 levels: utils -> backend -> SRS4Autism
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# NEW TARGET: data/knowledge_graph_store
KG_PATH = PROJECT_ROOT / "data" / "knowledge_graph_store"

class OxigraphManager:
    _store_instance = None

    @classmethod
    def get_store(cls):
        if cls._store_instance is None:
            # Ensure the directory exists
            KG_PATH.mkdir(parents=True, exist_ok=True)
            
            try:
                print(f"📦 Connecting to Oxigraph DB at: {KG_PATH}")
                cls._store_instance = oxigraph.Store(str(KG_PATH))
            except Exception as e:
                print(f"❌ Failed to initialize Oxigraph: {e}")
                # Fallback to memory only if disk fails (prevents crashing)
                cls._store_instance = oxigraph.Store() 
        
        return cls._store_instance

def get_kg_store():
    return OxigraphManager.get_store()
