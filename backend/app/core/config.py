from pathlib import Path
import os

def find_project_root():
    current = Path(__file__).resolve()
    for parent in current.parents:
        # 寻找包含 .git 或 backend 文件夹的目录作为真正的根
        if (parent / ".git").exists() or (parent / "backend").exists() and not (parent / "app").exists():
            return parent
    return current.parent.parent.parent # 兜底

PROJECT_ROOT = find_project_root()

DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
CONTENT_DB_DIR = DATA_DIR / "content_db"

PROFILES_DIR.mkdir(parents=True, exist_ok=True)
CONTENT_DB_DIR.mkdir(parents=True, exist_ok=True)

PROFILES_FILE = PROFILES_DIR / "child_profiles.json"
CARDS_FILE = CONTENT_DB_DIR / "approved_cards.json"
ANKI_PROFILES_FILE = PROFILES_DIR / "anki_profiles.json"
CHAT_HISTORY_FILE = CONTENT_DB_DIR / "chat_history.json"
PROMPT_TEMPLATES_FILE = PROFILES_DIR / "prompt_templates.json"
WORD_KP_CACHE_FILE = CONTENT_DB_DIR / "word_kp_cache.json"
MODEL_CONFIG_FILE = PROJECT_ROOT / "config" / "model_config.json"
ENGLISH_SIMILARITY_FILE = CONTENT_DB_DIR / "english_word_similarity.json"
GRAMMAR_CORRECTIONS_FILE = CONTENT_DB_DIR / "grammar_corrections.json"
# Vocabulary and Data Files
HSK_VOCAB_FILE = PROJECT_ROOT / "data" / "content_db" / "hsk_vocabulary.csv"
CEFR_VOCAB_FILE = PROJECT_ROOT.parent / "olp-en-cefrj" / "cefrj-vocabulary-profile-1.5.csv"
CONCRETENESS_DATA_FILE = PROJECT_ROOT / "data" / "content_db" / "concreteness_ratings.csv"
AOAS_DATA_FILE = PROJECT_ROOT / "data" / "content_db" / "aoa_ratings.csv"
ENGLISH_KG_MAP_FILE = PROJECT_ROOT / "data" / "content_db" / "english_kg_map.json"

DATABASE_PATH = CONTENT_DB_DIR / "srs4autism.db"

