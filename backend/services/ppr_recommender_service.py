"""
PPR Recommendation Service for CUMA
Integrates the Personalized PageRank recommender with database and Fuseki.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json
import math
import networkx as nx
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "recommendation_engine"))

from ppr_recommender import (
    load_similarity_graph,
    build_personalization_vector,
    run_ppr,
    load_word_metadata,
    build_label_index,
    _map_word_to_node_id,
    _normalize_node_id,
    WordMetadata,
)

# Default configuration
DEFAULT_CONFIG = {
    "alpha": 0.5,
    "beta_ppr": 1.0,
    "beta_concreteness": 0.8,
    "beta_frequency": 0.3,
    "beta_aoa_penalty": 2.0,
    "beta_intercept": 0.0,
    "mental_age": 8.0,
    "aoa_buffer": 2.0,
    "min_similarity": 0.0,
    "exclude_multiword": True,
    "top_n": 50,
}


class PPRRecommenderService:
    """Service for PPR-based English word recommendations."""
    
    def __init__(
        self,
        similarity_file: Path,
        kg_endpoint: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize PPR recommender service.
        
        Args:
            similarity_file: Path to english_word_similarity.json
            kg_endpoint: Optional Fuseki endpoint (if None, uses TTL file)
            config: Configuration dictionary (see DEFAULT_CONFIG)
        """
        self.similarity_file = Path(similarity_file)
        self.kg_endpoint = kg_endpoint
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        
        # Load similarity graph
        print(f"📊 Loading similarity graph from {self.similarity_file}...")
        self.graph, self.labels = load_similarity_graph(
            self.similarity_file, 
            min_similarity=self.config["min_similarity"]
        )
        print(f"   ✅ Loaded {self.graph.number_of_nodes():,} nodes, {self.graph.number_of_edges():,} edges")
        
        # Word metadata and label index will be loaded on demand
        self.word_metadata: Optional[Dict[str, WordMetadata]] = None
        self.label_index: Optional[Dict[str, str]] = None
    
    def load_kg_metadata(self, kg_file: Optional[Path] = None) -> None:
        """Load word metadata from KG file or Fuseki."""
        if self.word_metadata is not None:
            return  # Already loaded
        
        if kg_file:
            print(f"📚 Loading word metadata from {kg_file}...")
            self.word_metadata = load_word_metadata(kg_file)
            self.label_index = build_label_index(self.word_metadata)
            print(f"   ✅ Loaded metadata for {len(self.word_metadata):,} words")
        elif self.kg_endpoint:
            # TODO: Load from Fuseki SPARQL queries
            raise NotImplementedError("Loading metadata from Fuseki not yet implemented")
        else:
            raise ValueError("Either kg_file or kg_endpoint must be provided")
    
    def get_mastered_word_ids(
        self, 
        mastered_words: List[str],
        profile_id: Optional[str] = None
    ) -> Tuple[List[str], List[str]]:
        """
        Map mastered word texts to KG node IDs.
        
        Returns:
            (matched_ids, unmatched_words)
        """
        if self.label_index is None:
            raise ValueError("KG metadata not loaded. Call load_kg_metadata() first.")
        
        matched = []
        unmatched = []
        
        for word in mastered_words:
            node_id = _map_word_to_node_id(word, self.label_index)
            if node_id:
                # Normalize node ID to match graph
                normalized_id = _normalize_node_id(node_id)
                matched.append(normalized_id)
            else:
                unmatched.append(word)
        
        return matched, unmatched
    
    def get_recommendations(
        self,
        mastered_words: List[str],
        profile_id: Optional[str] = None,
        exclude_words: Optional[List[str]] = None,
        **override_config
    ) -> List[Dict[str, Any]]:
        """
        Get PPR-based recommendations.
        
        Args:
            mastered_words: List of mastered word texts
            profile_id: Optional profile ID (for logging)
            exclude_words: Optional list of words to exclude
            **override_config: Configuration overrides
        
        Returns:
            List of recommendation dictionaries with:
            - word: word text
            - node_id: KG node ID
            - score: P(Recommend) probability
            - log_ppr: log-transformed PPR score
            - z_concreteness: z-scored concreteness
            - log_frequency: log-transformed frequency
            - aoa_penalty: AoA penalty value
        """
        # Merge config overrides
        config = {**self.config, **override_config}
        
        # Map mastered words to node IDs
        matched_ids, unmatched = self.get_mastered_word_ids(mastered_words, profile_id)
        
        if not matched_ids:
            return []
        
        if unmatched and len(unmatched) <= 10:
            print(f"   ⚠️  {len(unmatched)} mastered words could not be mapped (e.g., {', '.join(unmatched[:5])})")
        
        # Build seed weights
        seed_weights = {node_id: 1.0 for node_id in matched_ids}
        
        # Build personalization vector
        personalization = build_personalization_vector(self.graph, seed_weights)
        
        # Run PPR
        scores = run_ppr(self.graph, personalization, alpha=config["alpha"])
        
        # Calculate statistics for transformations
        all_concreteness = [
            meta.concreteness
            for meta in self.word_metadata.values()
            if meta.concreteness is not None
        ]
        conc_mean = sum(all_concreteness) / len(all_concreteness) if all_concreteness else 3.0
        conc_std = (
            math.sqrt(
                sum((c - conc_mean) ** 2 for c in all_concreteness) / len(all_concreteness)
            )
            if len(all_concreteness) > 1
            else 1.5
        )
        
        # Transform functions
        def transform_ppr(raw_ppr: float) -> float:
            return math.log10(raw_ppr + 1e-10)
        
        def transform_concreteness(value: Optional[float]) -> float:
            if value is None:
                return 0.0
            return (value - conc_mean) / conc_std
        
        def transform_frequency(rank: Optional[int]) -> float:
            if not rank or rank <= 0:
                return 0.0
            return -math.log10(rank + 1)
        
        def calculate_aoa_penalty(aoa: Optional[float], mental_age: Optional[float]) -> float:
            if aoa is None or mental_age is None:
                return 0.0
            return max(0.0, aoa - mental_age)
        
        # Build excluded node IDs
        excluded_node_ids = set()
        if exclude_words:
            for word in exclude_words:
                node_id = _map_word_to_node_id(word, self.label_index)
                if node_id:
                    excluded_node_ids.add(_normalize_node_id(node_id))
        
        # Score candidates
        candidates = []
        for node_id, raw_score in scores.items():
            # Normalize node ID
            normalized_id = _normalize_node_id(node_id)
            
            if normalized_id in seed_weights:
                continue
            if normalized_id in excluded_node_ids:
                continue
            
            meta = self.word_metadata.get(normalized_id)
            if not meta:
                continue
            
            # Filter multi-word if requested
            if config.get("exclude_multiword"):
                label = meta.label or self.labels.get(normalized_id, normalized_id)
                if " " in label or "-" in label:
                    continue
            
            # Filter by AoA
            if (
                config.get("mental_age") is not None
                and meta.age_of_acquisition is not None
                and meta.age_of_acquisition > config["mental_age"] + config["aoa_buffer"]
            ):
                continue
            
            # Transform features
            ppr_transformed = transform_ppr(raw_score)
            conc_transformed = transform_concreteness(meta.concreteness)
            freq_transformed = transform_frequency(meta.frequency_rank)
            aoa_penalty = calculate_aoa_penalty(meta.age_of_acquisition, config.get("mental_age"))
            
            # Calculate logit z-score
            z = (
                config["beta_intercept"]
                + config["beta_ppr"] * ppr_transformed
                + config["beta_concreteness"] * conc_transformed
                + config["beta_frequency"] * freq_transformed
                - config["beta_aoa_penalty"] * aoa_penalty
            )
            
            # Convert to probability
            final_score = 1.0 / (1.0 + math.exp(-z))
            
            label = meta.label or self.labels.get(normalized_id, normalized_id)
            candidates.append({
                "word": label,
                "node_id": normalized_id,
                "score": final_score,
                "log_ppr": ppr_transformed,
                "z_concreteness": conc_transformed,
                "log_frequency": freq_transformed,
                "aoa_penalty": aoa_penalty,
                "concreteness": meta.concreteness,
                "age_of_acquisition": meta.age_of_acquisition,
                "frequency_rank": meta.frequency_rank,
            })
        
        # Sort by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        return candidates[:config.get("top_n", 50)]


# Global service instance (lazy-loaded)
_service_instance: Optional[PPRRecommenderService] = None


def get_ppr_service(
    similarity_file: Optional[Path] = None,
    kg_file: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
) -> PPRRecommenderService:
    """Get or create global PPR service instance."""
    global _service_instance
    
    if _service_instance is None:
        if similarity_file is None:
            similarity_file = PROJECT_ROOT / "data" / "content_db" / "english_word_similarity.json"
        if kg_file is None:
            kg_file = PROJECT_ROOT / "knowledge_graph" / "world_model_english.ttl"
        
        # Ensure paths are absolute
        similarity_file = similarity_file.resolve()
        kg_file = kg_file.resolve()
        
        # Check if files exist
        if not similarity_file.exists():
            raise FileNotFoundError(f"Similarity file not found: {similarity_file}")
        if not kg_file.exists():
            raise FileNotFoundError(f"KG file not found: {kg_file}")
        
        try:
            _service_instance = PPRRecommenderService(
                similarity_file=similarity_file,
                config=config
            )
            _service_instance.load_kg_metadata(kg_file=kg_file)
        except Exception as e:
            # Reset instance on error so it can be retried
            _service_instance = None
            raise RuntimeError(f"Failed to initialize PPR service: {str(e)}") from e
    
    return _service_instance

