
from fastapi import APIRouter, HTTPException, Request, Depends
import requests
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
import csv
import io
from collections import defaultdict
import os
import sys
import traceback
from sqlalchemy.orm import Session

# Fix pathing to find the scripts folder
PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_DIR))

from ..core.config import HSK_VOCAB_FILE, CEFR_VOCAB_FILE, CONCRETENESS_DATA_FILE, AOAS_DATA_FILE, ENGLISH_SIMILARITY_FILE, ENGLISH_KG_MAP_FILE, PROFILES_FILE, PROJECT_ROOT # PROJECT_ROOT added back as it's used for other files
from ..utils.pinyin_utils import get_standard_pinyin, get_pinyin_tone, strip_pinyin_tones
from ..utils.oxigraph_utils import get_kg_store # Added new import

# CORRECT IMPORTS FROM THE SCRIPTS FOLDER
from scripts.knowledge_graph.curious_mario_recommender import KnowledgeGraphService, CuriousMarioRecommender, RecommenderConfig, KnowledgeNode

from database.kg_client import KnowledgeGraphClient
from services.ppr_recommender_service import get_ppr_service
from services.chinese_ppr_recommender_service import get_chinese_ppr_service
from database.db import get_db
from database.services import ProfileService
# Use absolute import for integrated service to avoid relative path confusion
from services.integrated_recommender_service import IntegratedRecommenderService

router = APIRouter(prefix="/kg")
router_integrated = APIRouter(prefix="/recommendations")

# ... load_json_file and query_sparql remain as they were ...

def get_english_semantic_similarity() -> Dict[str, List[Dict[str, Any]]]:
    global _english_similarity_cache
    if _english_similarity_cache is not None:
        return _english_similarity_cache
    if not ENGLISH_SIMILARITY_FILE.exists():
        return {}
    try:
        with ENGLISH_SIMILARITY_FILE.open("r", encoding="utf-8") as f:
            payload = json.load(f)
            _english_similarity_cache = payload.get("similarities", {})
            meta = payload.get("metadata", {})
            # FIX: Missing quote was here
            print(f"🧠 Similarity loaded (threshold={meta.get('threshold')})")
    except Exception:
        _english_similarity_cache = {}
    return _english_similarity_cache

# ... find_learning_frontier and get_recommendations ...

# FIX: In all the recommendation routes (PPR, Integrated, etc),
# replace 'beta_intercept' with 'beta_intercept'.
# Python variables cannot have dashes.
from pydantic import BaseModel

class RecommendationRequest(BaseModel):
    mastered_words: List[str]
    profile_id: str
    concreteness_weight: Optional[float] = 0.5
    mental_age: Optional[float] = None

class EnglishRecommendationRequest(BaseModel):
    mastered_words: List[str]
    profile_id: str
    concreteness_weight: Optional[float] = 0.5
    mental_age: Optional[float] = None

class PPRRecommendationRequest(BaseModel):
    profile_id: str
    mastered_words: Optional[List[str]] = None
    exclude_words: Optional[List[str]] = None
    alpha: Optional[float] = 0.5
    beta_ppr: Optional[float] = 1.0
    beta_concreteness: Optional[float] = 0.8
    beta_frequency: Optional[float] = 0.3
    beta_aoa_penalty: Optional[float] = 2.0
    beta_intercept: Optional[float] = 0.0
    mental_age: Optional[float] = 8.0
    aoa_buffer: Optional[float] = 2.0
    exclude_multiword: Optional[bool] = True
    top_n: Optional[int] = 50
    max_level: Optional[int] = 6  # Added to support CEFR filtering (1=A1...6=C2)

class ChinesePPRRecommendationRequest(BaseModel):
    profile_id: str
    mastered_words: Optional[List[str]] = None
    exclude_words: Optional[List[str]] = None
    alpha: Optional[float] = 0.5
    beta_ppr: Optional[float] = 1.0
    beta_concreteness: Optional[float] = 0.8
    beta_frequency: Optional[float] = 0.3
    beta_aoa_penalty: Optional[float] = 2.0
    beta_intercept: Optional[float] = 0.0
    mental_age: Optional[float] = 8.0
    aoa_buffer: Optional[float] = 2.0
    exclude_multiword: Optional[bool] = True
    top_n: Optional[int] = 50
    max_hsk_level: Optional[int] = 6

class IntegratedRecommendationRequest(BaseModel):
    profile_id: str
    language: Optional[str] = "zh"
    mastered_words: Optional[List[str]] = None
    alpha: Optional[float] = None
    beta_ppr: Optional[float] = None
    beta_concreteness: Optional[float] = None
    beta_frequency: Optional[float] = None
    beta_aoa_penalty: Optional[float] = None
    beta_intercept: Optional[float] = None
    mental_age: Optional[float] = None
    aoa_buffer: Optional[float] = None
    exclude_multiword: Optional[bool] = None
    top_n: Optional[int] = None
    max_hsk_level: Optional[int] = None

class WordRecommendation(BaseModel):
    word: str
    hsk_level: Optional[int]
    cefr_level: Optional[str]
    concreteness: Optional[float]
    frequency: Optional[float]
    frequency_rank: Optional[int]
    age_of_acquisition: Optional[float]
    score: float
    is_mastered: bool = False



def load_json_file(file_path: Path, default: Any = None):
    """Load JSON data from file, return default if file doesn't exist"""
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return default if default is not None else []


# Knowledge Graph Configuration - Using Oxigraph embedded store
def query_sparql(sparql_query: str, output_format: str = "text/csv", timeout: int = 30):
    """Execute a SPARQL query against Oxigraph knowledge graph store."""
    try:
        kg_client = KnowledgeGraphClient()
        result = kg_client.query(sparql_query)
        
        # If CSV format was requested, convert JSON to CSV
        if output_format == "text/csv":
            if "results" not in result or "bindings" not in result.get("results", {}):
                return ""
            
            bindings = result["results"]["bindings"]
            if not bindings:
                return ""
            
            # Get variable names
            vars = result.get("head", {}).get("vars", [])
            if not vars:
                return ""
            
            # Convert to CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(vars)  # Header
            
            for binding in bindings:
                row = []
                for var in vars:
                    if var in binding:
                        value = binding[var].get("value", "")
                        row.append(value)
                    else:
                        row.append("")
                writer.writerow(row)
            
            return output.getvalue()
        
        # Otherwise return JSON format
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Knowledge graph query failed: {str(e)}")

# Cached semantic similarity map for English words
_english_similarity_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None


def get_english_semantic_similarity() -> Dict[str, List[Dict[str, Any]]]:
    """Load precomputed semantic similarity map for English words."""
    global _english_similarity_cache
    if _english_similarity_cache is not None:
        return _english_similarity_cache

    if not ENGLISH_SIMILARITY_FILE.exists():
        print(f"⚠️  English similarity file not found at {ENGLISH_SIMILARITY_FILE}")
        _english_similarity_cache = {}
        return _english_similarity_cache

    try:
        with ENGLISH_SIMILARITY_FILE.open("r", encoding="utf-8") as f:
            payload = json.load(f)
            _english_similarity_cache = payload.get("similarities", {})
            meta = payload.get("metadata", {})
            print(f"🧠 Loaded English semantic similarity graph "
                  f"(words={len(_english_similarity_cache)}, "
                  f"model={meta.get('model')}, "
                  f"threshold={meta.get('threshold')}")
    except Exception as exc:
        print(f"⚠️  Failed to load English similarity file: {exc}")
        _english_similarity_cache = {}

    return _english_similarity_cache

def find_learning_frontier(mastered_words: List[str], target_level: int = 1, top_n: int = 50, concreteness_weight: float = 0.5, mental_age: Optional[float] = None):
    """
    Find words to learn next using the 'Learning Frontier' algorithm.
    """
    # Step 1: Query metadata
    sparql = f"""
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?word ?word_text ?pinyin ?hsk ?concreteness ?aoa WHERE {{
        ?word a srs-kg:Word ;
              rdfs:label ?word_text ;
              srs-kg:hskLevel ?hsk .
        FILTER (lang(?word_text) = "zh")
        FILTER (!STRSTARTS(?word_text, "synset:"))
        FILTER (!STRSTARTS(?word_text, "concept:"))
        OPTIONAL {{ ?word srs-kg:pinyin ?pinyin }}
        OPTIONAL {{ ?word srs-kg:concreteness ?concreteness }}
        OPTIONAL {{ ?word srs-kg:ageOfAcquisition ?aoa }}
    }}
    """
    
    csv_result = query_sparql(sparql, "text/csv")
    words_data = defaultdict(lambda: {'pinyin': '', 'hsk': None, 'concreteness': None, 'aoa': None, 'chars': set()})
    
    if not csv_result.strip(): # Check if csv_result is empty or just whitespace
        print("⚠️  SPARQL query for words_data returned no results. Returning empty list.")
        return []

    reader = csv.reader(io.StringIO(csv_result))
    next(reader)  # Skip header
    
    mastered_set = set(mastered_words)
    
    for row in reader:
        if len(row) >= 4:
            word_text = row[1]
            pinyin = row[2] if len(row) > 2 else ''
            try:
                hsk = int(float(row[3])) if row[3] else None
                conc = float(row[4]) if len(row) > 4 and row[4] else None
                aoa = float(row[5]) if len(row) > 5 and row[5] else None

                words_data[word_text].update({
                    'pinyin': pinyin,
                    'hsk': hsk,
                    'concreteness': conc,
                    'aoa': aoa
                })
            except:
                continue

    # Step 2: Get character prerequisites
    sparql_chars = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?word_label ?char_label WHERE {
        ?word a srs-kg:Word ; srs-kg:composedOf ?char ; rdfs:label ?word_label .
        ?char rdfs:label ?char_label .
        FILTER (lang(?word_label) = "zh")
    }
    """
    try:
        char_csv = query_sparql(sparql_chars, "text/csv")
        char_reader = csv.reader(io.StringIO(char_csv))
        next(char_reader)
        for row in char_reader:
            if len(row) >= 2 and row[0] in words_data:
                words_data[row[0]]['chars'].add(row[1])
    except: pass

    # Step 3: Scoring
    scored_words = []
    hsk_weight = 1.0 - concreteness_weight
    aoa_ceiling = (mental_age + 2.0) if mental_age else 99
    
    for word, data in words_data.items():
        if word in mastered_set: continue
        if data['aoa'] and data['aoa'] > aoa_ceiling: continue
        
        # HSK Score - filter out words without HSK level (treat as advanced/rare)
        hsk_val = 0.0
        if not data['hsk']:
            # No HSK level = treat as advanced/rare, skip
            continue
        if data['hsk'] == target_level: hsk_val = 100.0
        elif data['hsk'] == target_level + 1: hsk_val = 50.0
        elif data['hsk'] > target_level + 1: continue # Too difficult
        
        # Concreteness (1-5 scale normalized to 0-100)
        conc_val = ((data['concreteness'] - 1.0) / 4.0 * 100.0) if data['concreteness'] else 50.0
        
        # Character Mastery Bonus
        char_bonus = 0.0
        if data['chars']:
            known = sum(1 for c in data['chars'] if c in mastered_set)
            char_bonus = 50.0 * (known / len(data['chars']))
            
        final_score = (hsk_val * hsk_weight) + (conc_val * concreteness_weight) + char_bonus
        
        scored_words.append({
            'word': word,
            'pinyin': data['pinyin'],
            'hsk': data['hsk'],
            'score': final_score,
            'known_chars': sum(1 for c in data['chars'] if c in mastered_set),
            'total_chars': len(data['chars']),
            'concreteness': data['concreteness'],
            'age_of_acquisition': data['aoa']
        })
    
    scored_words.sort(key=lambda x: x['score'], reverse=True)
    return scored_words[:top_n]

@router.post("/recommendations")
async def get_recommendations(request: RecommendationRequest):
    """
    Get vocabulary recommendations based on mastered words and knowledge graph.
    
    Returns top 50 words to learn next based on the Learning Frontier algorithm.
    """
    try:
        # Validate input
        if not request.mastered_words:
            return {
                "recommendations": [],
                "message": "No mastered words provided"
            }
        
        print(f"📚 Getting recommendations for {len(request.mastered_words)} mastered words")
        
        # Get recommendations
        # Dynamically determine target level based on mastery rates
        # Find the "learning frontier" - first level where mastery < 80%
        target_level = 3  # Default fallback
        
        print(f"🎯 Determining optimal target level...")
        
        if request.mastered_words:
            # Get mastery rate per level
            mastery_by_level = defaultdict(lambda: {'total': 0, 'mastered': 0})
            
            try:
                sparql = """
                PREFIX srs-kg: <http://srs4autism.com/schema/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                SELECT ?word ?word_text ?hsk WHERE {
                    ?word a srs-kg:Word ;
                          rdfs:label ?word_text ;
                          srs-kg:hskLevel ?hsk .
                    FILTER (lang(?word_text) = "zh")
                    FILTER (!STRSTARTS(?word_text, "synset:"))
                    FILTER (!STRSTARTS(?word_text, "concept:"))
                }
                """

                print(f"   🔍 Querying knowledge graph (WITH FILTERS APPLIED - v2)...")
                csv_result = query_sparql(sparql, "text/csv")

                if not csv_result.strip():  # Check if csv_result is empty or just whitespace
                    print("   ⚠️  SPARQL query for mastery rates returned no results.")
                    # No words in KG, cannot determine mastery. Keep default target_level.
                else:
                    reader = csv.reader(io.StringIO(csv_result))
                    next(reader)  # Skip header

                    mastered_set = set(request.mastered_words)

                    # DEBUG: Sample first 10 words to see what we're getting
                    debug_count = 0
                    synset_count = 0
                    concept_count = 0

                    for row in reader:
                        if len(row) >= 3:
                            word_text = row[1]  # word_text is second column

                            # DEBUG: Sample first few words
                            if debug_count < 5:
                                print(f"      DEBUG: word_text = '{word_text}'")
                                debug_count += 1

                            # Count synsets and concepts that got through
                            if word_text.startswith("synset:"):
                                synset_count += 1
                            elif word_text.startswith("concept:"):
                                concept_count += 1

                            try:
                                hsk = int(row[2]) if len(row) > 2 and row[2] else None
                            except ValueError:
                                hsk = None

                            if hsk:
                                mastery_by_level[hsk]['total'] += 1
                                if word_text in mastered_set:
                                    mastery_by_level[hsk]['mastered'] += 1

                    print(f"      DEBUG: Found {synset_count} synsets and {concept_count} concepts (filters NOT working!)")
                
                print(f"   📊 Mastery rates by level:")
                for level in sorted(mastery_by_level.keys()):
                    if mastery_by_level[level]['total'] > 0:
                        rate = mastery_by_level[level]['mastered'] / mastery_by_level[level]['total']
                        print(f"      HSK {level}: {mastery_by_level[level]['mastered']}/{mastery_by_level[level]['total']} ({rate*100:.1f}%)")
                
                # Find learning frontier (first level < 80% mastery)
                for level in sorted(mastery_by_level.keys()):
                    if mastery_by_level[level]['total'] > 0:
                        rate = mastery_by_level[level]['mastered'] / mastery_by_level[level]['total']
                        if rate < 0.8:  # Less than 80% mastered
                            target_level = level
                            print(f"   🎯 Learning frontier: HSK {target_level} ({rate*100:.1f}% mastered)")
                            break
            except Exception as e:
                print(f"   ⚠️  Warning: Could not determine optimal target level: {e}")
                import traceback
                traceback.print_exc()
                target_level = 1  # Conservative default
        
        print(f"   📌 Using target_level = {target_level}")
        
        # Get concreteness weight from request (default 0.5 = balanced)
        concreteness_weight = request.concreteness_weight if hasattr(request, 'concreteness_weight') else 0.5
        concreteness_weight = max(0.0, min(1.0, concreteness_weight))  # Clamp to 0-1
        print(f"   ⚖️  Concreteness weight: {concreteness_weight:.2f} (HSK weight: {1.0 - concreteness_weight:.2f})")
        
        # Get mental_age from profile if available
        mental_age = None
        if request.profile_id:
            profiles = load_json_file(PROFILES_FILE, [])
            profile = next((p for p in profiles if p.get('id') == request.profile_id or p.get('name') == request.profile_id), None)
            if profile and profile.get('mental_age'):
                try:
                    mental_age = float(profile['mental_age'])
                    print(f"   🧠 Using mental_age={mental_age:.1f} from profile for AoA filtering")
                except (ValueError, TypeError):
                    pass
        
        recommendations = find_learning_frontier(
            mastered_words=request.mastered_words,
            target_level=target_level,
            top_n=50,  # Changed from 20 to 50
            concreteness_weight=concreteness_weight,
            mental_age=mental_age
        )
        
        print(f"   ✅ Found {len(recommendations)} recommendations")
        
        return {
            "recommendations": recommendations,
            "message": f"Found {len(recommendations)} recommendations"
        }
    except HTTPException:
        raise  # Re-raise HTTPException to be handled by FastAPI
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")



@router.post("/english-recommendations")
async def get_english_recommendations(request: EnglishRecommendationRequest):
    """
    Get English vocabulary recommendations based on mastered words and knowledge graph.
    
    Returns top 50 English words to learn next based on the Learning Frontier algorithm.
    Uses CEFR levels and concreteness scoring.
    """
    try:
        # Validate input
        if not request.mastered_words:
            return {
                "recommendations": [],
                "message": "No mastered words provided"
            }
        
        print(f"📚 Getting English recommendations for {len(request.mastered_words)} mastered words")
        
        # Build mastery vector from profile's mastered words
        # We need to map word texts to KG node IDs
        mastered_set = set(w.lower().strip() for w in request.mastered_words)
        
        # Create config for English vocabulary
        # Slider: 0.0 = Max Frequency (Utility), 1.0 = Max Concreteness (Ease)
        slider_value = max(0.0, min(1.0, request.concreteness_weight or 0.5))
        print(f"   ⚖️  Slider position: {slider_value:.2f} (0.0=Frequency/Utility, 1.0=Concreteness/Ease)")
        print(f"   📋 CEFR acts as hard filter: only showing current level and +1")
        
        config = RecommenderConfig(
            node_types=("srs-kg:Word",),
            concreteness_weight=slider_value,  # This is now the slider position, not a weight
            top_n=50,
            auto_detect_language=True,
            mental_age=request.mental_age  # Pass mental age for AoA filtering
        )
        print(f"   ⚖️  Config slider: {config.concreteness_weight:.2f}")
        print(f"   🧠 Semantic similarity weight: {config.semantic_similarity_weight:.2f}")
        english_similarity_map = get_english_semantic_similarity()
        
        # Fetch nodes to build mastery vector
        # Override fetch_nodes to filter for English words only (those with CEFR levels)
        kg_service = KnowledgeGraphService(config)
        
        # Custom query to get only English words (those with CEFR levels)
        node_types = " ".join(config.node_types)
        query = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?node ?label ?hsk ?cefr ?concreteness ?frequency ?freqRank ?aoa ?prereq WHERE {{
            VALUES ?type {{ {node_types} }}
            ?node a ?type ;
                  rdfs:label ?label .
            # Filter for English words: must have CEFR level (English words) OR English language tag
            OPTIONAL {{ ?node srs-kg:cefrLevel ?cefr }}
            OPTIONAL {{ ?node srs-kg:hskLevel ?hsk }}
            OPTIONAL {{ ?node srs-kg:concreteness ?concreteness }}
            OPTIONAL {{ ?node srs-kg:frequency ?frequency }}
            OPTIONAL {{ ?node srs-kg:frequencyRank ?freqRank }}
            OPTIONAL {{ ?node srs-kg:ageOfAcquisition ?aoa }}
            OPTIONAL {{ ?node srs-kg:requiresPrerequisite ?prereq }}
            # Only include words with CEFR level (English words)
            FILTER(BOUND(?cefr))
            FILTER (!STRSTARTS(STR(?label), "synset:"))
            FILTER (!STRSTARTS(STR(?label), "concept:"))
        }}
        """
        
        # Use KnowledgeGraphClient instead of direct Fuseki endpoint
        kg_client = KnowledgeGraphClient()
        data = kg_client.query(query)
        
        # Parse nodes from SPARQL results
        nodes = {}
        for row in data.get("results", {}).get("bindings", []):
            node_iri = row["node"]["value"]
            label = row["label"]["value"]
            # Extract node_id from IRI
            node_id = node_iri.split("/")[-1] if "/" in node_iri else node_iri
            
            node = KnowledgeNode(
                node_id=node_id,
                iri=node_iri,
                label=label,
                hsk_level=None,
                cefr_level=None,
                concreteness=None,
                frequency=None,
                frequency_rank=None,
                age_of_acquisition=None,
                prerequisites=[],
            )
            
            if "hsk" in row and row["hsk"]["value"]:
                try:
                    node.hsk_level = int(float(row["hsk"]["value"]))
                except ValueError:
                    pass
            
            if "cefr" in row and row["cefr"]["value"]:
                node.cefr_level = str(row["cefr"]["value"]).upper()
            
            if "concreteness" in row and row["concreteness"]["value"]:
                try:
                    node.concreteness = float(row["concreteness"]["value"])
                except (ValueError, TypeError):
                    pass

            if "frequency" in row and row["frequency"]["value"]:
                try:
                    node.frequency = float(row["frequency"]["value"])
                except (ValueError, TypeError):
                    pass

            if "freqRank" in row and row["freqRank"]["value"]:
                try:
                    node.frequency_rank = int(float(row["freqRank"]["value"]))
                except (ValueError, TypeError):
                    pass
            
            if "aoa" in row and row["aoa"]["value"]:
                try:
                    node.age_of_acquisition = float(row["aoa"]["value"])
                except (ValueError, TypeError):
                    pass
            
            if "prereq" in row and row["prereq"]["value"]:
                prereq_id = row["prereq"]["value"].split("/")[-1] if "/" in row["prereq"]["value"] else row["prereq"]["value"]
                if prereq_id not in node.prerequisites:
                    node.prerequisites.append(prereq_id)
            
            nodes[node_id] = node
        
        print(f"   📊 Fetched {len(nodes)} English words from knowledge graph")
        
        if len(nodes) == 0:
            return {
                "recommendations": [],
                "message": "No English words found in knowledge graph. Please ensure the English vocabulary has been populated.",
                "learning_frontier": None
            }
        
        # Build mastery vector: mark words as mastered if they're in the profile
        mastery_vector = {}
        mastered_count = 0
        matched_words = []
        unmatched_words = []
        
        for node_id, node in nodes.items():
            # Check if word label matches any mastered word (case-insensitive)
            word_lower = node.label.lower().strip()
            if word_lower in mastered_set:
                mastery_vector[node_id] = 1.0  # Fully mastered
                mastered_count += 1
                matched_words.append(node.label)
            else:
                mastery_vector[node_id] = 0.0  # Not mastered
        
        # Show some examples of matched/unmatched words for debugging
        if mastered_count > 0:
            print(f"   ✅ Matched {mastered_count} mastered words (examples: {matched_words[:5]})")
        else:
            # Check if any words from mastered_set exist in nodes (for debugging)
            sample_mastered = list(mastered_set)[:5]
            sample_node_labels = [node.label.lower() for node in list(nodes.values())[:10]]
            print(f"   ⚠️  No matches found. Sample mastered words: {sample_mastered}")
            print(f"   ⚠️  Sample node labels: {sample_node_labels}")
            print(f"   ⚠️  Total mastered words provided: {len(mastered_set)}")
        
        print(f"   📊 Built mastery vector: {mastered_count} mastered out of {len(mastery_vector)} words")
        
        # Create recommender and find learning frontier
        recommender = CuriousMarioRecommender(config)
        # Reset debug counter for this request
        recommender._debug_logged_count = 0
        language = recommender._detect_language(nodes)
        print(f"   🌐 Detected language: {language}")
        learning_frontier = recommender._find_learning_frontier(nodes, mastery_vector, language)
        
        if learning_frontier:
            print(f"   🎯 Learning frontier: CEFR {learning_frontier}")
        
        # Generate recommendations
        mastered_node_ids = {
            node_id for node_id, mastery in mastery_vector.items()
            if mastery >= config.mastery_threshold
        }
        semantic_weight = config.semantic_similarity_weight
        recommendations = []
        for node_id, node in nodes.items():
            mastery = mastery_vector.get(node_id, 0.0)
            
            # Skip if already mastered
            if mastery >= config.mastery_threshold:
                continue
            
            # Skip if no CEFR level (not in CEFR-J vocabulary)
            if not node.cefr_level:
                continue
            
            # Calculate score
            prereq_mastery = 1.0  # No prerequisites for now
            score = recommender._score_candidate(node, mastery, prereq_mastery, language, learning_frontier)
            semantic_boost = 0.0
            if english_similarity_map:
                similar_entries = english_similarity_map.get(node_id, [])
                for neighbour in similar_entries:
                    neighbour_id = neighbour.get("neighbor_id")
                    if not neighbour_id:
                        continue
                    if neighbour_id in mastered_node_ids:
                        semantic_boost += neighbour.get("similarity", 0.0)
            
            # Factor in semantic boost
            score += semantic_boost * semantic_weight
            
            recommendations.append(WordRecommendation(
                word=node.label,
                hsk_level=node.hsk_level,
                cefr_level=node.cefr_level,
                concreteness=node.concreteness,
                frequency=node.frequency,
                frequency_rank=node.frequency_rank,
                age_of_acquisition=node.age_of_acquisition,
                score=score,
                is_mastered=(mastery >= config.mastery_threshold)
            ))

        # Sort and return top N
        recommendations = sorted(recommendations, key=lambda r: r.score, reverse=True)[:config.top_n]
        
        print(f"   ✅ Found {len(recommendations)} English recommendations")
        
        return {
            "recommendations": recommendations,
            "message": f"Found {len(recommendations)} English recommendations",
            "learning_frontier": learning_frontier
        }
    
    except HTTPException:
        raise  # Re-raise HTTPException to be handled by FastAPI
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@router.post("/ppr-recommendations")
async def get_ppr_recommendations(request: PPRRecommendationRequest):
    """
    Get English vocabulary recommendations using Personalized PageRank (PPR) algorithm.
    
    Uses semantic similarity graph, mastered words, and probability-based scoring.
    Returns top N words to learn next based on PPR scores combined with concreteness,
    frequency, and age of acquisition.
    """
    try:
        print(f"📚 Getting PPR recommendations for profile '{request.profile_id}'")
        
        # Load mastered words from database if not provided
        mastered_words = request.mastered_words
        if not mastered_words:
            db = next(get_db())
            try:
                mastered_words = ProfileService.get_mastered_words(db, request.profile_id, 'en')
                print(f"   📘 Loaded {len(mastered_words)} mastered words from database")
            finally:
                db.close()
        
        if not mastered_words:
            return {
                "recommendations": [],
                "message": "No mastered words found. Add some words to get recommendations."
            }
        
        # Build configuration from request
        config = {}
        if request.alpha is not None:
            config["alpha"] = request.alpha
        if request.beta_ppr is not None:
            config["beta_ppr"] = request.beta_ppr
        if request.beta_concreteness is not None:
            config["beta_concreteness"] = request.beta_concreteness
        if request.beta_frequency is not None:
            config["beta_frequency"] = request.beta_frequency
        if request.beta_aoa_penalty is not None:
            config["beta_aoa_penalty"] = request.beta_aoa_penalty
        if request.beta_intercept is not None:
            config["beta_intercept"] = request.beta_intercept
        if request.mental_age is not None:
            config["mental_age"] = request.mental_age
        if request.aoa_buffer is not None:
            config["aoa_buffer"] = request.aoa_buffer
        if request.exclude_multiword is not None:
            config["exclude_multiword"] = request.exclude_multiword
        if request.top_n is not None:
            config["top_n"] = request.top_n
        if request.max_level is not None:
            config["max_level"] = request.max_level
        
        # Get PPR service (lazy-loaded singleton)
        similarity_file = PROJECT_ROOT / "data" / "content_db" / "english_word_similarity.json"
        # Use rescued KG with 18K English words
        kg_file = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"
        
        service = get_ppr_service(
            similarity_file=similarity_file,
            kg_file=kg_file,
            config=config
        )
        
        # Get recommendations
        recommendations = service.get_recommendations(
            mastered_words=mastered_words,
            profile_id=request.profile_id,
            exclude_words=request.exclude_words,
            **config
        )
        
        print(f"   ✅ Found {len(recommendations)} recommendations")
        
        return {
            "recommendations": recommendations,
            "message": f"Found {len(recommendations)} recommendations",
            "config_used": config
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting PPR recommendations: {str(e)}")


@router.post("/chinese-ppr-recommendations")
async def get_chinese_ppr_recommendations(request: ChinesePPRRecommendationRequest):
    """
    Get Chinese vocabulary recommendations using Personalized PageRank (PPR) algorithm.
    
    Uses semantic similarity graph, mastered words, and probability-based scoring.
    Returns top N words to learn next based on PPR scores combined with concreteness,
    frequency, and age of acquisition.
    """
    try:
        print(f"📚 Getting Chinese PPR recommendations for profile '{request.profile_id}'")
        
        # Load mastered words from database if not provided
        mastered_words = request.mastered_words
        if not mastered_words:
            db = next(get_db())
            try:
                mastered_words = ProfileService.get_mastered_words(db, request.profile_id, 'zh')
                print(f"   📘 Loaded {len(mastered_words)} mastered Chinese words from database")
            finally:
                db.close()
        
        if not mastered_words:
            return {
                "recommendations": [],
                "message": "No mastered words found. Add some words to get recommendations."
            }
        
        # Build configuration from request
        config = {}
        if request.alpha is not None:
            config["alpha"] = request.alpha
        if request.beta_ppr is not None:
            config["beta_ppr"] = request.beta_ppr
        if request.beta_concreteness is not None:
            config["beta_concreteness"] = request.beta_concreteness
        if request.beta_frequency is not None:
            config["beta_frequency"] = request.beta_frequency
        if request.beta_aoa_penalty is not None:
            config["beta_aoa_penalty"] = request.beta_aoa_penalty
        if request.beta_intercept is not None:
            config["beta_intercept"] = request.beta_intercept
        if request.mental_age is not None:
            config["mental_age"] = request.mental_age
        if request.aoa_buffer is not None:
            config["aoa_buffer"] = request.aoa_buffer
        if request.exclude_multiword is not None:
            config["exclude_multiword"] = request.exclude_multiword
        if request.top_n is not None:
            config["top_n"] = request.top_n
        
        # Get Chinese PPR service (lazy-loaded singleton)
        similarity_file = PROJECT_ROOT / "data" / "content_db" / "chinese_word_similarity.json"
        # Use rescued KG with 27K Chinese words, characters, and concepts
        kg_file = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"
        
        service = get_chinese_ppr_service(
            similarity_file=similarity_file,
            kg_file=kg_file,
            config=config
        )
        
        # Get recommendations
        recommendations = service.get_recommendations(
            mastered_words=mastered_words,
            profile_id=request.profile_id,
            exclude_words=request.exclude_words,
            **config
        )
        
        print(f"   ✅ Found {len(recommendations)} Chinese recommendations")
        
        return {
            "recommendations": recommendations,
            "message": f"Found {len(recommendations)} recommendations",
            "config_used": config
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting Chinese PPR recommendations: {str(e)}")


@router_integrated.post("/integrated")
async def get_integrated_recommendations(
    request: IntegratedRecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Get integrated recommendations using three-stage funnel:
    1. Candidate Generation: PPR + ZPD Filter
    2. Campaign Manager: Inventory Logic (allocates slots based on profile ratios)
    3. Synergy Matcher: (skipped for now)
    
    Returns recommendations allocated according to profile's daily capacity and target ratios.
    """
    try:
        print(f" 🎯 Getting integrated recommendations for profile '{request.profile_id}'")
        
        # Get profile
        profile = ProfileService.get_by_id(db, request.profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{request.profile_id}' not found")
        
        # Initialize integrated recommender
        recommender = IntegratedRecommenderService(profile, db)
        
        # Build PPR config overrides
        ppr_config = {}
        if request.alpha is not None:
            ppr_config["alpha"] = request.alpha
        if request.beta_ppr is not None:
            ppr_config["beta_ppr"] = request.beta_ppr
        if request.beta_concreteness is not None:
            ppr_config["beta_concreteness"] = request.beta_concreteness
        if request.beta_frequency is not None:
            ppr_config["beta_frequency"] = request.beta_frequency
        if request.beta_aoa_penalty is not None:
            ppr_config["beta_aoa_penalty"] = request.beta_aoa_penalty
        if request.beta_intercept is not None:
            ppr_config["beta_intercept"] = request.beta_intercept
        if request.mental_age is not None:
            ppr_config["mental_age"] = request.mental_age
        if request.aoa_buffer is not None:
            ppr_config["aoa_buffer"] = request.aoa_buffer
        if request.exclude_multiword is not None:
            ppr_config["exclude_multiword"] = request.exclude_multiword
        if request.top_n is not None:
            ppr_config["top_n"] = request.top_n
        if request.max_hsk_level is not None and request.language == "zh":
            ppr_config["max_hsk_level"] = request.max_hsk_level
        
        # Get recommendations
        recommendations = recommender.get_recommendations(
            language=request.language,
            mastered_words=request.mastered_words,
            **ppr_config
        )
        
        # Convert to dict format for JSON response
        recommendations_dict = [
            {
                "node_id": rec.node_id,
                "label": rec.label,
                "content_type": rec.content_type,
                "language": rec.language,
                "score": rec.score,
                "ppr_score": rec.ppr_score,
                "zpd_score": rec.zpd_score,
                "mastery": rec.mastery,
                "hsk_level": rec.hsk_level,
                "cefr_level": rec.cefr_level,
                "prerequisites": rec.prerequisites or [],
                "missing_prereqs": rec.missing_prereqs or []
            }
            for rec in recommendations
        ]
        
        print(f"   ✅ Found {len(recommendations)} integrated recommendations")
        print(f"   📊 Allocation: {recommender.vocab_slots} vocab, {recommender.grammar_slots} grammar")
        print(f"   📊 Ratios: {recommender.vocab_ratio:.1%} vocab, {recommender.grammar_ratio:.1%} grammar")
        
        return {
            "recommendations": recommendations_dict,
            "allocation": {
                "daily_capacity": recommender.daily_capacity,
                "vocab_slots": recommender.vocab_slots,
                "grammar_slots": recommender.grammar_slots,
                "vocab_ratio": recommender.vocab_ratio,
                "grammar_ratio": recommender.grammar_ratio
            },
            "message": f"Found {len(recommendations)} recommendations"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
