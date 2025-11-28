# Curious Mario Architecture Documentation

**Project Status:** Personal Script Collection → Commercial Desktop Application  
**Last Updated:** 2025-01-27

---

## Executive Summary

Curious Mario (formerly SRS4Autism) is an AI-powered learning co-pilot for personalized education, particularly designed for autistic children. The system combines Spaced Repetition Systems (SRS), Knowledge Graphs, and Large Language Models to create adaptive learning content.

**Current Architecture:** Monolithic Python backend (FastAPI) + React frontend, with SQLite database and RDF Knowledge Graph.

---

## 1. Core Logic

### 1.1 Knowledge Graph Generation

**Location:** `scripts/knowledge_graph/`

**Key Scripts:**
- `populate_from_cwn.py` - Populates Chinese vocabulary from CwnGraph (Chinese WordNet)
- `populate_grammar.py` - Loads Chinese grammar points from JSON into KG
- `populate_english_vocab.py` - Populates English vocabulary with CEFR levels
- `populate_english_grammar.py` - Loads English grammar from CEFR-J CSV
- `build_english_word_similarity.py` - Generates semantic similarity graph using spaCy
- `build_chinese_word_similarity.py` - Generates Chinese word similarity using spaCy/Tencent embeddings
- `integrate_aoa_kuperman.py` - Integrates Age of Acquisition data for English words
- `integrate_chinese_metadata.py` - Integrates SUBTLEX-CH (frequency), MELD-SCH (concreteness), CCLOOW (AoA)
- `enrich_with_wikidata.py` - Enriches concepts with Wikidata Q-IDs for cross-language alignment
- `propagate_aoa_to_chinese.py` - Propagates AoA from English to Chinese via CC-CEDICT translations
- `merge_kg_files.py` - Merges multiple KG files into a single merged graph

**Output Files:**
- `knowledge_graph/world_model_cwn.ttl` - Chinese knowledge graph
- `knowledge_graph/world_model_english.ttl` - English knowledge graph
- `knowledge_graph/world_model_merged.ttl` - Merged graph (used by Fuseki)
- `data/content_db/english_word_similarity.json` - Precomputed English word similarity
- `data/content_db/chinese_word_similarity.json` - Precomputed Chinese word similarity

**Dependencies:**
- RDFLib (RDF/Turtle parsing)
- CwnGraph (Chinese WordNet)
- spaCy (word embeddings)
- CC-CEDICT (Chinese-English dictionary)

### 1.2 Analysis Engine

**Location:** `scripts/analysis/`, `scripts/recommendation_engine/`

**Components:**
- **PPR Recommender** (`scripts/recommendation_engine/ppr_recommender.py`)
  - Personalized PageRank algorithm for word recommendations
  - Uses semantic similarity graphs
  - Considers mastered words, Anki review history, concreteness, frequency, AoA
  - Probability-based scoring using logit transformation

- **Learning Frontier Algorithm** (in `backend/app/main.py`)
  - Chinese word recommendations based on HSK level, known characters, concreteness
  - English word recommendations based on CEFR level, frequency, concreteness

**Services:**
- `backend/services/ppr_recommender_service.py` - English PPR recommender service
- `backend/services/chinese_ppr_recommender_service.py` - Chinese PPR recommender service

### 1.3 LLM Integration

**Location:** `backend/app/main.py`, `agentic/`, `agent/`

**LLM Calls:**
- **Google Gemini API** (`google.generativeai`)
  - Content generation (flashcards, explanations)
  - Image generation (via Gemini 2.5 Pro)
  - Knowledge lookups (fallback when KG data missing)
  - Chat assistant responses

**Configuration:**
- API Key: `backend/gemini.env` (GEMINI_API_KEY)
- Model: `models/gemini-2.5-flash` (default, configurable via GEMINI_MODEL)
- Image Model: `models/gemini-2.5-flash-image-generation` (when available)

**Agentic System:**
- `agentic/agent.py` - Main agent orchestrator
- `agentic/memory.py` - Agent memory management
- `agentic/tools.py` - Agent tool definitions
- `agentic/principles.py` - Learning principles store
- `agent/content_generator.py` - Content generation logic
- `agent/conversation_handler.py` - Chat conversation handling

### 1.4 Content Generation

**Location:** `agent/content_generation/`, `scripts/content_generation/`

**Features:**
- Flashcard generation (basic, reverse, cloze, interactive cloze)
- Image description generation
- Grammar point explanations
- Example sentence generation

---

## 2. State Management

### 2.1 Database (SQLite)

**Location:** `data/srs4autism.db`

**Schema:**
- **`profiles`** - User profiles (children)
  - Fields: id, name, dob, gender, address, school, neighborhood, interests, character_roster, verbal_fluency, passive_language_level, mental_age, raw_input, extracted_data
- **`mastered_words`** - Mastered vocabulary (Chinese and English)
  - Fields: id, profile_id, word, language ('zh' or 'en'), added_at
- **`mastered_grammar`** - Mastered grammar points
  - Fields: id, profile_id, grammar_point_id, language, added_at
- **`approved_cards`** - Curated flashcards awaiting sync to Anki
  - Fields: id, profile_id, front, back, card_type, status, etc.
- **`chat_messages`** - Chat history with AI assistant
  - Fields: id, profile_id, content, role, timestamp, mentions
- **`character_recognition_notes`** - Character recognition notes from .apkg
  - Fields: id, note_id, character, display_order, fields (JSON)
- **`audit_log`** - Audit trail for all changes

**Database Layer:**
- `backend/database/models.py` - SQLAlchemy models
- `backend/database/db.py` - Database connection and initialization
- `backend/database/services.py` - Service layer (ProfileService, CardService, ChatService)

### 2.2 Knowledge Graph Storage

**Format:** RDF/Turtle (.ttl files)

**Storage:**
- `knowledge_graph/world_model_cwn.ttl` - Chinese KG
- `knowledge_graph/world_model_english.ttl` - English KG
- `knowledge_graph/world_model_merged.ttl` - Merged KG (used by Fuseki)

**SPARQL Endpoint:** Apache Jena Fuseki (runs locally, typically on port 3030)

**Backup System:**
- `scripts/knowledge_graph/kg_backup.py` - Automatic timestamped backups before KG updates
- Backups stored in `knowledge_graph/` with timestamp suffix

### 2.3 Legacy JSON Files (Still in Use)

**Location:** `data/content_db/`, `data/profiles/`

**Files:**
- `data/content_db/approved_cards.json` - Legacy card storage (being migrated)
- `data/content_db/chat_history.json` - Legacy chat history (being migrated)
- `data/profiles/prompt_templates.json` - Prompt templates
- `data/content_db/word_kp_cache.json` - Word-to-knowledge-point cache
- `data/content_db/grammar_corrections.json` - Grammar correction mappings

**Note:** Profile data has been migrated to SQLite, but some JSON files are still used for specific features.

### 2.4 Media Files

**Location:** `media/`

**Structure:**
- `media/audio/` - Generated TTS audio files
- `media/images/` - User-uploaded images
- `media/generated/` - AI-generated images
- `media/character_recognition/` - Character recognition images (from .apkg)
- `media/visual_images/` - Visual concept images

**Naming Convention:** `cm_[Type]_[ContentID]_[Variant].[ext]` (e.g., `cm_char_I2_a1b2c3d4.png`)

**Anki Integration:** Media files uploaded to Anki's `collection.media` directory via AnkiConnect's `storeMediaFile` API.

---

## 3. Interfaces

### 3.1 Backend API (FastAPI)

**Entry Point:** `backend/app/main.py`

**Server:** `backend/run.py` (uses uvicorn)

**Port:** 8000 (default, configurable via API_PORT env var)

**Key Endpoints:**

**Profile Management:**
- `GET /profiles` - List all profiles
- `POST /profiles` - Create profile
- `GET /profiles/{id}` - Get profile
- `PUT /profiles/{id}` - Update profile
- `DELETE /profiles/{id}` - Delete profile

**Mastered Content:**
- `GET /vocabulary/mastered` - Get mastered words
- `POST /vocabulary/master` - Add mastered word
- `DELETE /vocabulary/master` - Remove mastered word
- `GET /vocabulary/grammar` - Get grammar points
- `GET /kg/grammar-recommendations` - Get grammar recommendations

**Recommendations:**
- `POST /kg/recommendations` - Chinese word recommendations (Learning Frontier)
- `POST /kg/english-recommendations` - English word recommendations (Learning Frontier)
- `POST /kg/ppr-recommendations` - English PPR recommendations
- `POST /kg/chinese-ppr-recommendations` - Chinese PPR recommendations

**Content:**
- `GET /cards` - Get approved cards
- `POST /cards` - Create card
- `PUT /cards/{id}` - Update card
- `POST /cards/{id}/sync` - Sync card to Anki
- `POST /cards/{id}/generate-image` - Generate image for card

**Character Recognition:**
- `GET /character-recognition/notes` - Get character recognition notes
- `POST /character-recognition/sync` - Sync notes to Anki
- `POST /character-recognition/master` - Mark character as mastered

**Chat:**
- `POST /chat` - Send chat message
- `GET /chat/history` - Get chat history

**Agentic Planning:**
- `POST /agentic/plan` - Generate learning plan

**CORS:** Configured for `http://localhost:3000` and `http://127.0.0.1:3000`

### 3.2 Frontend (React)

**Location:** `frontend/`

**Entry Point:** `frontend/src/App.js`

**Key Components:**
- `App.js` - Main application router
- `ProfileManager.js` - Profile management UI
- `ChildProfileSettings.js` - Profile editing
- `LanguageContentManager.js` - Language content management (vocabulary, grammar, character recognition)
- `MasteredWordsManager.js` - Chinese mastered words
- `MasteredEnglishWordsManager.js` - English mastered words
- `MasteredGrammarManager.js` - Grammar mastery tracking
- `CardCuration.js` - Card approval/curation interface
- `ChatAssistant.js` - AI chat interface
- `CharacterRecognition.js` - Character recognition note management
- `TemplateManager.js` - Prompt template management

**API Base URL:** `http://localhost:8000` (configurable via `REACT_APP_API_URL` env var)

**Build:** `npm run build` (outputs to `frontend/build/`)

**Development:** `npm start` (runs on port 3000)

### 3.3 Anki Integration

**Location:** `anki_integration/anki_connect.py`

**Protocol:** AnkiConnect REST API (JSON-RPC over HTTP)

**Default URL:** `http://localhost:8765`

**Key Methods:**
- `ping()` - Check Anki connection
- `add_note(deck, note_type, fields)` - Add note to Anki
- `store_media_file(filename, base64_data)` - Upload media to Anki
- `get_deck_names()` - List decks
- `create_deck(name)` - Create deck
- `get_review_history()` - Get Anki review history

**Note Types:**
- Custom note types defined in Anki (e.g., "CUMA - Chinese Recognition")
- Templates stored in `anki_integration/templates/`

---

## 4. External Dependencies

### 4.1 AnkiConnect

**Type:** Anki Add-on (must be installed in Anki)

**Purpose:** Bridge between Curious Mario and Anki

**Installation:** https://ankiweb.net/shared/info/2055492159

**Requirements:**
- Anki must be running
- AnkiConnect add-on must be installed
- Default port: 8765

### 4.2 Google Cloud / Gemini API

**Service:** Google Generative AI (Gemini)

**Purpose:**
- Content generation
- Image generation
- Knowledge lookups
- Chat responses

**Configuration:**
- API Key: Stored in `backend/gemini.env`
- Model: `models/gemini-2.5-flash` (default)
- Image Model: `models/gemini-2.5-flash-image-generation`

**Dependencies:**
- `google-generativeai` Python package

### 4.3 Apache Jena Fuseki

**Type:** SPARQL endpoint server

**Location:** `apache-jena-fuseki-4.9.0/`

**Purpose:** Serves Knowledge Graph via SPARQL queries

**Default Port:** 3030

**Datasets:**
- `world_model` - Merged knowledge graph

**Startup:** `restart_fuseki.sh` (or manually run `fuseki-server`)

### 4.4 Data Sources

**External Data:**
- **CwnGraph** (`/Users/maxent/src/CwnGraph/`) - Chinese WordNet
- **CC-CEDICT** (`/Users/maxent/src/cc-cedict-1.0.3/`) - Chinese-English dictionary
- **HSK Vocabulary** (`/Users/maxent/src/complete-hsk-vocabulary/`) - HSK word lists
- **CEFR-J** (`/Users/maxent/src/olp-en-cefrj/`) - English grammar and vocabulary profiles
- **SUBTLEX-CH** - Chinese word frequency (downloaded separately)
- **MELD-SCH** - Chinese concreteness ratings (downloaded separately)
- **CCLOOW** - Chinese Age of Acquisition (downloaded separately, or propagated from English)

**Note:** Some data sources are in sibling directories (`../`), which will break on other machines.

### 4.5 Python Dependencies

**Key Packages:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM
- `rdflib` - RDF/Turtle parsing
- `google-generativeai` - Gemini API
- `spacy` - NLP/word embeddings
- `networkx` - Graph algorithms (for PPR)
- `scipy` - Scientific computing
- `requests` - HTTP client
- `pydantic` - Data validation

**Requirements:** `backend/requirements.txt`

---

## 5. Hard-Coded Strings and Paths

### 5.1 File Paths

**Critical Paths (Will Break on Other Machines):**

```python
# backend/app/main.py
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
PROFILES_FILE = str(PROJECT_ROOT / "data" / "profiles" / "child_profiles.json")
CARDS_FILE = str(PROJECT_ROOT / "data" / "content_db" / "approved_cards.json")
# ... many more
```

**External Data Paths (Hard-coded sibling directories):**
- `PROJECT_ROOT.parent / "CwnGraph"` - CwnGraph location
- `PROJECT_ROOT.parent / "cc-cedict-1.0.3"` - CC-CEDICT location
- `PROJECT_ROOT.parent / "olp-en-cefrj"` - CEFR-J location
- `PROJECT_ROOT.parent / "complete-hsk-vocabulary"` - HSK vocabulary location

**Recommendation:** Move to configuration file or environment variables.

### 5.2 Network Addresses

**Hard-coded URLs:**

```javascript
// frontend/src/*.js
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
```

```python
# anki_integration/anki_connect.py
def __init__(self, url: str = "http://localhost:8765"):
```

```python
# backend/app/main.py
allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"]
```

**Fuseki SPARQL Endpoint:**
```python
# backend/app/main.py (implicit in SPARQL queries)
FUSEKI_URL = "http://localhost:3030/world_model/query"
```

**Recommendation:** Move all URLs to environment variables or configuration file.

### 5.3 Database Paths

**Hard-coded:**
```python
# backend/database/db.py
DB_PATH = PROJECT_ROOT / "data" / "srs4autism.db"
backup_path = PROJECT_ROOT / "data" / "backups" / f"srs4autism_{timestamp}.db"
```

**Recommendation:** Use user data directory (e.g., `~/.curious-mario/` on Linux/Mac, `%APPDATA%\CuriousMario` on Windows).

### 5.4 Media Paths

**Hard-coded:**
```python
# backend/app/main.py
media_dir = PROJECT_ROOT / "media" / "character_recognition"
```

**Anki Media Directory:**
- Currently relies on AnkiConnect to handle media storage
- No explicit path to Anki's `collection.media` directory

**Recommendation:** Make media directory configurable, or use user data directory.

### 5.5 Language Strings

**Hard-coded UI Text:**

**English:**
- "Failed to load profiles"
- "Profile created successfully"
- "Synced X cards successfully"
- Many more in frontend components

**Chinese:**
- "中文", "英文", "汉字", "词汇", "语法", "语用" (in `LanguageContentManager.js`)
- Various error messages and labels

**Recommendation:** Implement i18n (internationalization) system (e.g., react-i18next).

### 5.6 API Keys and Secrets

**Current Storage:**
- `backend/gemini.env` - Gemini API key
- `backend/google-credentials.json` - Google Cloud credentials (if used)

**Recommendation:**
- Use secure credential storage (OS keychain, encrypted config)
- Never commit secrets to version control
- Provide setup wizard for first-time configuration

### 5.7 Default Values

**Hard-coded Defaults:**
```python
# backend/app/main.py
mental_age: Optional[float] = 8.0  # Default mental age
alpha: Optional[float] = 0.5  # PPR teleport probability
beta_ppr: Optional[float] = 1.0  # PPR weight
# ... many more algorithm parameters
```

**Recommendation:** Move to configuration file with user-editable defaults.

### 5.8 File Names

**Hard-coded Filenames:**
- `语言语文__识字__全部.apkg` - Character recognition deck
- `chinese_grammar_knowledge_graph.json` - Grammar data
- `english_word_similarity.json` - Similarity data

**Recommendation:** Use configuration to specify data file locations.

---

## 6. Migration Recommendations for Commercial Desktop App

### 6.1 Configuration System

**Create:** `config/config.yaml` or `config/settings.json`

**Should Include:**
- Data directory paths (user-configurable)
- API endpoints (defaults, but configurable)
- External data source paths (or download instructions)
- Default algorithm parameters
- UI language preferences
- API keys (encrypted storage)

### 6.2 User Data Directory

**Standard Locations:**
- **Linux:** `~/.local/share/curious-mario/`
- **macOS:** `~/Library/Application Support/Curious Mario/`
- **Windows:** `%APPDATA%\Curious Mario`

**Structure:**
```
user-data/
├── database/
│   └── srs4autism.db
├── knowledge_graph/
│   ├── world_model_cwn.ttl
│   ├── world_model_english.ttl
│   └── world_model_merged.ttl
├── media/
│   ├── audio/
│   ├── images/
│   └── character_recognition/
├── backups/
└── logs/
```

### 6.3 Installation & Setup

**First-Time Setup:**
1. Install Anki and AnkiConnect add-on
2. Configure API keys (Gemini)
3. Download/configure external data sources (or bundle them)
4. Initialize database and knowledge graphs
5. Set user preferences (language, default parameters)

**Data Migration:**
- Provide migration tool for existing installations
- Backup existing data before migration

### 6.4 Internationalization (i18n)

**Implementation:**
- Use `react-i18next` for frontend
- Use `gettext` or similar for backend
- Store translations in `locales/` directory
- Support: English, Chinese (Simplified), Chinese (Traditional)

### 6.5 Error Handling

**Current State:** Many hard-coded error messages

**Recommendation:**
- Centralized error message system
- User-friendly error messages (not technical stack traces)
- Error codes for support/debugging
- Logging to user-accessible log files

### 6.6 Documentation

**User Documentation:**
- Installation guide
- First-time setup wizard
- User manual
- Troubleshooting guide

**Developer Documentation:**
- API documentation (OpenAPI/Swagger)
- Architecture diagrams
- Contribution guidelines

---

## 7. Current Limitations & Technical Debt

### 7.1 Data Source Dependencies

**Issue:** External data sources in sibling directories (`../CwnGraph`, etc.)

**Impact:** Will not work on other machines without manual setup

**Solution:** Bundle data sources or provide download scripts

### 7.2 Mixed Storage Systems

**Issue:** Some data in SQLite, some in JSON files, some in TTL files

**Impact:** Inconsistent data access patterns, harder to maintain

**Solution:** Complete migration to SQLite for user data, keep TTL for KG

### 7.3 Hard-coded Paths

**Issue:** Many absolute paths relative to project root

**Impact:** Breaks when moved to different location

**Solution:** Use configuration system and user data directory

### 7.4 No User Authentication

**Issue:** Single-user system, no multi-user support

**Impact:** Cannot support multiple users on same machine

**Solution:** Add user accounts and authentication (if needed for commercial version)

### 7.5 Limited Error Recovery

**Issue:** Some operations can corrupt data (e.g., KG overwrites)

**Impact:** Data loss risk

**Solution:** Better backup system, transaction safety, data validation

---

## 8. Deployment Considerations

### 8.1 Desktop Application Packaging

**Options:**
- **Electron** - Package React frontend + Node.js backend
- **PyInstaller** - Package Python backend as executable
- **Tauri** - Lightweight alternative to Electron
- **Native Desktop** - Platform-specific (Qt, GTK, Cocoa)

**Recommendation:** Electron or Tauri for cross-platform support

### 8.2 Distribution

**Channels:**
- Direct download from website
- App stores (Mac App Store, Microsoft Store, Snap Store)
- Package managers (Homebrew, Chocolatey, apt)

### 8.3 Updates

**Mechanism:**
- Auto-update system (Electron: `electron-updater`)
- Manual download and install
- In-app update notifications

### 8.4 Licensing

**Considerations:**
- License key validation
- Feature gating (free vs. paid)
- Usage analytics (privacy-respecting)

---

## 9. File Structure Summary

```
SRS4Autism/
├── agent/                    # Agent logic (content generation, conversation)
├── agentic/                  # Agentic system (planner, memory, tools)
├── anki_integration/         # AnkiConnect client
├── apache-jena-fuseki-4.9.0/ # Fuseki SPARQL server
├── backend/
│   ├── app/
│   │   └── main.py          # FastAPI application (main entry point)
│   ├── database/             # SQLAlchemy models and services
│   ├── services/             # Business logic services
│   ├── run.py               # Server startup script
│   └── requirements.txt     # Python dependencies
├── config/                   # Configuration files (to be expanded)
├── data/                     # User data (database, JSON files, backups)
├── deployment/               # Deployment configurations
├── docs/                     # Documentation
├── frontend/                 # React application
├── knowledge_graph/          # RDF/Turtle knowledge graph files
├── media/                    # Media files (audio, images)
├── scripts/
│   ├── knowledge_graph/      # KG generation scripts
│   ├── recommendation_engine/ # Recommendation algorithms
│   └── analysis/             # Analysis tools
└── tools/                    # Utility tools
```

---

## 10. Next Steps for Commercialization

1. **Configuration System** - Implement centralized config management
2. **User Data Directory** - Move from project-relative to user data directory
3. **Internationalization** - Add i18n support
4. **Error Handling** - Improve error messages and recovery
5. **Documentation** - Create user and developer documentation
6. **Packaging** - Choose and implement desktop app packaging
7. **Testing** - Add comprehensive test suite
8. **Licensing** - Implement license key system (if needed)
9. **Updates** - Add auto-update mechanism
10. **Support** - Set up support channels and ticketing system

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-27


