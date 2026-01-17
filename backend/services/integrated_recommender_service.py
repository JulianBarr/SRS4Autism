"""
Integrated Recommender Service
Combines PPR recommendations with ZPD heuristic filtering and Campaign Manager (inventory logic).

Implements the three-stage funnel:
1. Candidate Generation: PPR + ZPD Filter
2. Campaign Manager: Inventory Logic (allocates slots based on configurable ratios)
3. Synergy Matcher: (skipped for now)
"""
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "knowledge_graph"))

from backend.services.chinese_ppr_recommender_service import (
    get_chinese_ppr_service,
    ChinesePPRRecommenderService
)
from backend.services.ppr_recommender_service import (
    get_ppr_service,
    PPRRecommenderService
)
from scripts.knowledge_graph.curious_mario_recommender import (
    CuriousMarioRecommender,
    RecommenderConfig,
    AnkiMasteryExtractor,
    KnowledgeGraphService,
    KnowledgeNode,
    _normalize_kg_id
)
from backend.database.models import Profile, MasteredWord
from backend.database.services import ProfileService
from sqlalchemy.orm import Session
import requests
from urllib.parse import quote, unquote


# Global defaults (can be overridden per profile)
DEFAULT_DAILY_CAPACITY = 20
DEFAULT_VOCAB_RATIO = 0.5
DEFAULT_GRAMMAR_RATIO = 0.5


@dataclass
class IntegratedRecommendation:
    """A recommendation from the integrated system."""
    node_id: str
    label: str
    content_type: str  # 'vocab' or 'grammar'
    language: str  # 'zh' or 'en'
    score: float
    ppr_score: Optional[float] = None
    zpd_score: Optional[float] = None
    mastery: float = 0.0
    hsk_level: Optional[int] = None
    cefr_level: Optional[str] = None
    prerequisites: List[str] = None
    missing_prereqs: List[str] = None


class IntegratedRecommenderService:
    """Integrated recommender combining PPR + ZPD + Campaign Manager."""
    
    def __init__(self, profile: Profile, db: Session):
        """
        Initialize integrated recommender for a specific profile.
        
        Args:
            profile: Profile model instance with recommender configuration
            db: Database session for querying mastered words
        """
        self.profile = profile
        self.db = db
        
        # Get recommender configuration (with defaults)
        self.daily_capacity = (
            profile.recommender_daily_capacity 
            if profile.recommender_daily_capacity is not None 
            else DEFAULT_DAILY_CAPACITY
        )
        self.vocab_ratio = (
            profile.recommender_vocab_ratio 
            if profile.recommender_vocab_ratio is not None 
            else DEFAULT_VOCAB_RATIO
        )
        self.grammar_ratio = (
            profile.recommender_grammar_ratio 
            if profile.recommender_grammar_ratio is not None 
            else DEFAULT_GRAMMAR_RATIO
        )
        
        # Normalize ratios (ensure they sum to 1.0)
        total_ratio = self.vocab_ratio + self.grammar_ratio
        if total_ratio > 0:
            self.vocab_ratio = self.vocab_ratio / total_ratio
            self.grammar_ratio = self.grammar_ratio / total_ratio
        else:
            # Fallback to 50/50 if both are 0
            self.vocab_ratio = 0.5
            self.grammar_ratio = 0.5
        
        # Calculate slot allocation
        self.vocab_slots = int(self.daily_capacity * self.vocab_ratio)
        self.grammar_slots = self.daily_capacity - self.vocab_slots  # Remaining slots go to grammar
        
        # Initialize ZPD recommender for mastery/prerequisite checking
        zpd_config = RecommenderConfig(
            anki_query='_KG_Map:*',  # Anki search syntax: field_name:* (no quotes, colon is field separator)
            kg_field_name="_KG_Map",
            fuseki_endpoint="http://localhost:3030/srs4autism/query",
            mastery_threshold=0.85,
            prereq_threshold=0.75,
            mental_age=profile.mental_age,
        )
        self.zpd_recommender = CuriousMarioRecommender(zpd_config)
    
    def get_recommendations(
        self,
        language: str = "zh",
        mastered_words: Optional[List[str]] = None,
        **ppr_config_overrides
    ) -> List[IntegratedRecommendation]:
        """
        Get integrated recommendations for the profile.
        
        Args:
            language: 'zh' for Chinese, 'en' for English
            mastered_words: List of mastered word texts (if None, fetched from profile)
            **ppr_config_overrides: Override PPR configuration parameters
        
        Returns:
            List of IntegratedRecommendation objects, sorted by score
        """
        # Stage 1: Candidate Generation (PPR + ZPD Filter)
        vocab_candidates, grammar_candidates = self._generate_candidates(
            language=language,
            mastered_words=mastered_words,
            **ppr_config_overrides
        )
        
        # Stage 2: Campaign Manager (Inventory Logic)
        final_recommendations = self._campaign_manager(
            vocab_candidates=vocab_candidates,
            grammar_candidates=grammar_candidates
        )
        
        return final_recommendations
    
    def _enhance_mastery_vector_with_characters(
        self,
        mastery_vector: Dict[str, float],
        language: str
    ) -> Dict[str, float]:
        """
        Enhance mastery vector with character mastery.
        Ensures IDs match the format found in world_model_rescued.ttl (char-汉)
        """
        enhanced = mastery_vector.copy()
        
        # 1. Get explicitly mastered characters from database
        mastered_chars_db = ProfileService.get_mastered_words(
            self.db,
            self.profile.id,
            'character'
        )
        
        # In rescued.ttl, characters are usually char-饭 (hyphen)
        for char_text in mastered_chars_db:
            # Clean ID: char-饭
            char_id = f"char-{char_text}"
            enhanced[char_id] = 1.0
        
        # 2. Infer character mastery from word mastery
        if language == "zh":
            mastered_words_list = ProfileService.get_mastered_words(self.db, self.profile.id, 'zh')
            
            if mastered_words_list:
                inferred_chars = set()
                for word in mastered_words_list:
                    for char in word:
                        if '\u4e00' <= char <= '\u9fff':
                            inferred_chars.add(char)
                
                inferred_count = 0
                for char_text in inferred_chars:
                    # USE HYPHEN to match Knowledge Graph: char-饭
                    char_id = f"char-{char_text}"

                    if char_id not in enhanced or enhanced[char_id] < 0.8:
                        enhanced[char_id] = 0.8 
                        inferred_count += 1
                
                print(f"      ✅ Inferred {inferred_count} characters as mastered from word composition")
        
        return enhanced
    
    def _generate_candidates(
        self,
        language: str,
        mastered_words: Optional[List[str]],
        **ppr_config_overrides
    ) -> Tuple[List[IntegratedRecommendation], List[IntegratedRecommendation]]:
        """
        Stage 1: Generate candidates using PPR + ZPD filtering.
        
        Returns:
            Tuple of (vocab_candidates, grammar_candidates)
        """
        # Get mastery vector from Anki
        mastery_vector = self.zpd_recommender.build_mastery_vector()
        
        # Enhance with character mastery (from DB and inferred from words)
        mastery_vector = self._enhance_mastery_vector_with_characters(
            mastery_vector,
            language
        )
        
        # Get PPR recommendations for vocabulary
        vocab_candidates = self._get_ppr_vocab_recommendations(
            language=language,
            mastered_words=mastered_words,
            mastery_vector=mastery_vector,
            **ppr_config_overrides
        )
        
        # Get grammar recommendations (using ZPD only for now, no PPR for grammar yet)
        grammar_candidates = self._get_grammar_recommendations(
            language=language,
            mastery_vector=mastery_vector
        )
        
        return vocab_candidates, grammar_candidates
    
    def _get_ppr_vocab_recommendations(
        self,
        language: str,
        mastered_words: Optional[List[str]],
        mastery_vector: Dict[str, float],
        **ppr_config_overrides
    ) -> List[IntegratedRecommendation]:
        """Get vocabulary recommendations from PPR, then apply ZPD filtering."""
        # Get mastered words if not provided
        if mastered_words is None:
            mastered_words = ProfileService.get_mastered_words(
                self.db,
                self.profile.id,
                language
            )
        
        # Get PPR recommendations
        if language == "zh":
            ppr_service = get_chinese_ppr_service()
            ppr_recommendations = ppr_service.get_recommendations(
                mastered_words=mastered_words,
                profile_id=self.profile.id,
                **ppr_config_overrides
            )
        else:
            ppr_service = get_ppr_service()
            ppr_recommendations = ppr_service.get_recommendations(
                mastered_words=mastered_words,
                profile_id=self.profile.id,
                **ppr_config_overrides
            )
        
        print(f"   📊 PPR returned {len(ppr_recommendations)} vocabulary recommendations")
        
        if not ppr_recommendations:
            print(f"   ⚠️  No PPR vocabulary recommendations - returning empty list")
            return []
        
        # Get KG nodes for prerequisite checking
        vocab_config = RecommenderConfig(
            anki_query='_KG_Map:*',
            kg_field_name="_KG_Map",
            fuseki_endpoint="http://localhost:3030/srs4autism/query",
            node_types=("srs-kg:Word",),
            mastery_threshold=0.85,
            prereq_threshold=0.75,
            mental_age=self.profile.mental_age,
        )
        kg_service = KnowledgeGraphService(vocab_config)
        raw_nodes = kg_service.fetch_nodes()
        
        # Create a lookup map using clean IDs (strip ns1:, srs-kg:, etc.)
        nodes = { k.split(':')[-1]: v for k, v in raw_nodes.items() }
        
        print(f"   📊 KG has {len(nodes)} Word nodes (normalized)")
        
        # Fallback to metadata cache if KG is empty
        use_metadata_fallback = len(nodes) == 0
        metadata_valid_node_ids = set()
        
        if use_metadata_fallback:
            print(f"   ⚠️  Live KG seems empty. Falling back to Metadata Cache for validation.")
            if ppr_service.word_metadata:
                metadata_valid_node_ids = set(ppr_service.word_metadata.keys())
                print(f"   ✅ Using metadata cache with {len(metadata_valid_node_ids):,} words")
            else:
                print(f"   ⚠️  Metadata cache not loaded for PPR service")
        
        # Apply ZPD filtering (prerequisites, mastery threshold)
        candidates = []
        skipped_no_node_id = 0
        skipped_mastered = 0
        skipped_no_node = 0
        skipped_prereqs = 0
        
        # --- 🕵️‍♂️ DEBUG: VISUALIZE ID MISMATCH ---
        print("\n🕵️‍♂️ DIAGNOSIS: ID Mismatch Check")
        if ppr_recommendations:
            test_id = ppr_recommendations[0].get("node_id", "")
            print(f"👉 PPR ID: '{test_id}'")
            if use_metadata_fallback and metadata_valid_node_ids:
                 # Check logic without srs-kg prefix just in case
                stripped_id = test_id.replace("srs-kg:", "")
                zh_id = stripped_id.replace("word-", "word-zh-")
                print(f"❓ Test (Stripped + -zh-): '{zh_id}' in Cache? -> {zh_id in metadata_valid_node_ids}")
        print("--------------------------------------------------\n")
        # ----------------------------------------
        
        for rec in ppr_recommendations:
            raw_node_id = rec.get("node_id", "")
            # CLEAN ID: 'word-zh-饭馆' (no srs-kg: prefix)
            node_id = raw_node_id.split(':')[-1]
            
            if not node_id:
                skipped_no_node_id += 1
                continue
            
            # 1. Check mastery (using Clean ID)
            mastery = mastery_vector.get(node_id, 0.0)
            if mastery >= self.zpd_recommender.config.mastery_threshold:
                skipped_mastered += 1
                continue

            # 2. Validation & Prerequisite Check
            node = None
            missing_prereqs = []

            if use_metadata_fallback:
                # --- METADATA VALIDATION (v2: supports both old and new URI formats) ---
                # Old format: srs-kg:word-{text} → word-{text} (after stripping prefix)
                # New format: srs-inst:word_zh_{pinyin} → word_zh_{pinyin} (after stripping prefix)
                # Cache keys may or may not have prefixes, so we need to try multiple patterns.

                # Handle standard rescued format
                base_id = node_id.split(':')[-1] if ':' in node_id else node_id

                found_id = None

                # Check 1: Exact match (base ID in cache)
                if base_id in metadata_valid_node_ids:
                    found_id = base_id

                # Check 2: Old format migration (word- → word-zh-)
                # For backward compatibility with old format during transition
                elif "word-" in base_id and not "word_zh_" in base_id:
                    legacy_fixed = base_id.replace("word-", "word-zh-")
                    if legacy_fixed in metadata_valid_node_ids:
                        found_id = legacy_fixed

                # Check 3: Full ID in cache (with prefix)
                elif node_id in metadata_valid_node_ids:
                    found_id = node_id

                # Check 4: Try alternate prefix (srs-kg: vs srs-inst:)
                elif not found_id:
                    # Try swapping prefixes for backward compatibility
                    if node_id.startswith("srs-kg:"):
                        alternate = node_id.replace("srs-kg:", "srs-inst:")
                        if alternate in metadata_valid_node_ids:
                            found_id = alternate
                    elif node_id.startswith("srs-inst:"):
                        alternate = node_id.replace("srs-inst:", "srs-kg:")
                        if alternate in metadata_valid_node_ids:
                            found_id = alternate

                if found_id:
                    node_id = found_id  # Success! Update ID to match cache
                else:
                    skipped_no_node += 1
                    continue
                # -----------------------------
                
                # Skip prerequisite checking when using fallback
                node = None
                missing_prereqs = []
                
            else:
                # Use Live KG
                node = nodes.get(node_id)
                if not node:
                    skipped_no_node += 1
                    continue
                
                # Robust prerequisite lookup: Always strip prefixes when checking mastery
                prereq_scores = []
                for pr in node.prerequisites:
                    # Clean the prerequisite ID from KG (e.g., ns1:char-饭 -> char-饭)
                    # Handle URL encoding (e.g. char-%E9%A5%AD -> char-饭)
                    clean_pr = unquote(pr.split(':')[-1])
                    prereq_scores.append(mastery_vector.get(clean_pr, 0.0))


                missing_prereqs = [
                    pr for pr, score in zip(node.prerequisites, prereq_scores)
                    if score < self.zpd_recommender.config.prereq_threshold
                ]
                
                if missing_prereqs:
                    skipped_prereqs += 1
                    continue

            # 3. Create Integrated Recommendation
            ppr_score = rec.get("score", rec.get("final_score", 0.0))
            
            # Robust label extraction
            label = rec.get("word", rec.get("label", node_id))
            if node:
                label = node.label
                hsk_level = node.hsk_level
                cefr_level = node.cefr_level
                prerequisites = node.prerequisites.copy()
            else:
                # Fallback data
                hsk_level = None
                cefr_level = None
                prerequisites = []

            candidates.append(IntegratedRecommendation(
                node_id=node_id,
                label=label,
                content_type="vocab",
                language=language,
                score=ppr_score,
                ppr_score=ppr_score,
                mastery=mastery,
                hsk_level=hsk_level,
                cefr_level=cefr_level,
                prerequisites=prerequisites,
                missing_prereqs=missing_prereqs
            ))
        
        print(f"   ✅ After ZPD filtering: {len(candidates)} vocabulary candidates")
        # --- PRINT THE REASONS FOR DROPPING CANDIDATES ---
        if skipped_no_node_id > 0: print(f"      ⚠️  Skipped {skipped_no_node_id} (missing node_id)")
        if skipped_mastered > 0: print(f"      ⚠️  Skipped {skipped_mastered} (already mastered)")
        if skipped_no_node > 0: print(f"      ⚠️  Skipped {skipped_no_node} (not found in Metadata Cache)")
        if skipped_prereqs > 0: print(f"      ⚠️  Skipped {skipped_prereqs} (prerequisites not met)")
        
        # Sort by score
        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates
    
    def _get_grammar_recommendations(
        self,
        language: str,
        mastery_vector: Dict[str, float]
    ) -> List[IntegratedRecommendation]:
        """Get grammar recommendations using ZPD heuristic (with manual file fallback)."""
        import re

        # 1. Try Loading from Live Knowledge Graph (Fuseki)
        config = RecommenderConfig(
            anki_query='_KG_Map:*',
            kg_field_name="_KG_Map",
            fuseki_endpoint="http://localhost:3030/srs4autism/query",
            node_types=("srs-kg:GrammarPoint",),
            mastery_threshold=0.85,
            prereq_threshold=0.75,
            mental_age=self.profile.mental_age,
        )

        kg_service = KnowledgeGraphService(config)
        nodes = kg_service.fetch_nodes()

        # 2. FALLBACK: If Live KG is empty, parse the TTL file manually
        if not nodes:
            # Check class-level cache to avoid re-parsing
            if hasattr(self.__class__, '_grammar_cache') and self.__class__._grammar_cache:
                nodes = self.__class__._grammar_cache
                print(f"   📊 Using Cached Grammar Nodes: {len(nodes)}")
            else:
                kg_file_path = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"
                print(f"   ⚠️  Live KG empty. Parsing grammar manually from {kg_file_path.name}...")

                parsed_nodes = {}
                current_id = None
                # Simple container for node data
                current_data = {"label": "Unknown", "prereqs": [], "cefr": "A1"}

                # Duck-Type Class for Nodes
                class FallbackNode:
                    def __init__(self, label, prerequisites, cefr_level):
                        self.label = label
                        self.prerequisites = prerequisites
                        self.cefr_level = cefr_level
                        self.hsk_level = None

                try:
                    with open(kg_file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()

                    for line in lines:
                        line = line.strip()

                        # 1. Detect Start of Grammar Point
                        # Matches: srs-inst:gp-B1-142-Reduplication of adjectives a srs-kg:GrammarPoint ;
                        if "a srs-kg:GrammarPoint" in line and line.startswith("srs-inst:"):
                            # Save previous node if exists
                            if current_id:
                                parsed_nodes[current_id] = FallbackNode(
                                    current_data["label"],
                                    current_data["prereqs"],
                                    current_data["cefr"]
                                )

                            # Extract ID (Everything before ' a srs-kg:GrammarPoint')
                            # e.g. "srs-inst:gp-B1-142-Reduplication of adjectives"
                            current_id = line.split(" a srs-kg:GrammarPoint")[0].strip()

                            # Reset data (Use part of ID as default label)
                            default_label = current_id.replace("srs-inst:", "")
                            current_data = {"label": default_label, "prereqs": [], "cefr": "A1"}

                        if current_id:
                            # 2. Extract Label (Prefer English)
                            # rdfs:label "Reduplication of adjectives"@en ;
                            if "rdfs:label" in line:
                                # Try to grab text inside quotes before @en
                                lbl_match = re.search(r'"([^"]+)"@en', line)
                                if lbl_match:
                                    current_data["label"] = lbl_match.group(1)
                                else:
                                    # Fallback to any quoted string
                                    lbl_match_any = re.search(r'"([^"]+)"', line)
                                    if lbl_match_any:
                                        current_data["label"] = lbl_match_any.group(1)

                            # 3. Extract CEFR Level
                            # srs-kg:cefrLevel "B1" ;
                            if "cefrLevel" in line:
                                lvl_match = re.search(r'"([^"]+)"', line)
                                if lvl_match:
                                    current_data["cefr"] = lvl_match.group(1)

                            # 4. Extract Prerequisites
                            # srs-kg:hasPrerequisite srs-inst:gp-XXX ;
                            if "hasPrerequisite" in line:
                                # Grab the ID that follows
                                pre_match = re.search(r'(srs-(?:inst|kg):[^;\s]+)', line)
                                if pre_match:
                                    current_data["prereqs"].append(pre_match.group(1))

                            # 5. End of Block (Line ends with .)
                            if line.endswith("."):
                                parsed_nodes[current_id] = FallbackNode(
                                    current_data["label"],
                                    current_data["prereqs"],
                                    current_data["cefr"]
                                )
                                current_id = None

                    # Cache the result
                    self.__class__._grammar_cache = parsed_nodes
                    nodes = parsed_nodes
                    print(f"   ✅ Manually parsed {len(nodes)} Grammar Points")

                except Exception as e:
                    print(f"   ❌ Error parsing grammar file: {e}")
                    nodes = {}

        # 3. Filter grammar points by ZPD criteria
        candidates = []
        for node_id, node in nodes.items():
            mastery = mastery_vector.get(node_id, 0.0)

            # Skip if mastered
            if mastery >= config.mastery_threshold:
                continue

            # Check prerequisites
            prereq_scores = [mastery_vector.get(pr, 0.0) for pr in node.prerequisites]
            missing_prereqs = [
                pr for pr, score in zip(node.prerequisites, prereq_scores)
                if score < config.prereq_threshold
            ]

            if missing_prereqs:
                continue

            # Score based on readiness (1 - mastery) and prerequisite mastery
            prereq_mastery = min(prereq_scores) if prereq_scores else 1.0
            readiness = 1.0 - mastery
            score = (readiness * 0.7) + (prereq_mastery * 0.3)

            candidates.append(IntegratedRecommendation(
                node_id=node_id,
                label=node.label,
                content_type="grammar",
                language=language,
                score=score,
                zpd_score=score,
                mastery=mastery,
                cefr_level=node.cefr_level,
                prerequisites=node.prerequisites.copy() if node.prerequisites else [],
                missing_prereqs=missing_prereqs
            ))

        # Sort by score
        candidates.sort(key=lambda x: x.score, reverse=True)
        print(f"   ✅ Found {len(candidates)} grammar candidates")
        return candidates

    def _campaign_manager(
        self,
        vocab_candidates: List[IntegratedRecommendation],
        grammar_candidates: List[IntegratedRecommendation]
    ) -> List[IntegratedRecommendation]:
        """
        Stage 2: Campaign Manager - Allocate slots based on target ratios.
        
        Args:
            vocab_candidates: Vocabulary candidates (already sorted by score)
            grammar_candidates: Grammar candidates (already sorted by score)
        
        Returns:
            Final list of recommendations allocated to slots
        """
        final_recommendations = []
        
        # Allocate vocabulary slots
        vocab_selected = vocab_candidates[:self.vocab_slots]
        final_recommendations.extend(vocab_selected)
        
        # Allocate grammar slots
        grammar_selected = grammar_candidates[:self.grammar_slots]
        final_recommendations.extend(grammar_selected)
        
        # Sort final list by score (optional - could keep separate)
        final_recommendations.sort(key=lambda x: x.score, reverse=True)
        
        return final_recommendations
