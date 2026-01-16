import pyoxigraph as oxigraph
from pathlib import Path
from typing import Optional
import logging

from backend.config import settings

logger = logging.getLogger(__name__)

# Global store instance
_store_instance: Optional[oxigraph.Store] = None

def get_oxigraph_store(store_path: Optional[str] = None) -> oxigraph.Store:
    """
    Get or initialize the singleton Oxigraph Store instance.
    """
    global _store_instance

    target_path = store_path or settings.kg_store_path

    if _store_instance is None:
        logger.info(f"Initializing Oxigraph store at {target_path}")
        try:
            # Ensure the directory exists
            Path(target_path).mkdir(parents=True, exist_ok=True)
            _store_instance = oxigraph.Store(path=target_path)
            logger.info("Oxigraph store initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Oxigraph store: {e}")
            raise

    return _store_instance

def initialize_store():
    """Explicitly initialize the store (e.g. at app startup)"""
    get_oxigraph_store()

