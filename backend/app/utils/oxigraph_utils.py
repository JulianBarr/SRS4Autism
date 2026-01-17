import pyoxigraph as oxigraph
from ..core.config import DATA_DIR
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class OxigraphManager:
    _store_instance = None

    @classmethod
    def get_store(cls):
        """
        Returns the global Oxigraph Store instance.
        Initializes it only once.
        """
        if cls._store_instance is None:
            # Ensure the path exists
            kg_path = DATA_DIR / "kg_store"
            kg_path.mkdir(parents=True, exist_ok=True)
            
            try:
                logger.info(f"📦 Initializing Oxigraph Store at: {kg_path}")
                cls._store_instance = oxigraph.Store(str(kg_path))
            except Exception as e:
                logger.error(f"❌ Failed to initialize Oxigraph Store: {e}")
                # Fallback to in-memory if disk-based fails
                cls._store_instance = oxigraph.Store() 
        
        return cls._store_instance

# Helper function for easy access
def get_kg_store():
    return OxigraphManager.get_store()

