"""
Chinese PPR Recommendation Service for CUMA
Integrates the Personalized PageRank recommender for Chinese words with database and Fuseki.
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json
import math
import networkx as nx
import re
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "recommendation_engine"))

from ppr_recommender import (
    load_similarity_graph,
    build_personalization_vector,
    run_ppr,
    _map_word_to_node_id,
    _normalize_node_id,
)

# Default configuration for Chinese
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
    "max_hsk_level": 4,
}


class ChineseWordMetadata:
    """Metadata for a Chinese word."""
    def __init__(
        self,
        node_id: str,
        label: str,
        hsk_level: Optional[int] = None,
        concreteness: Optional[float] = None,
        frequency_rank: Optional[int] = None,
        age_of_acquisition: Optional[float] = None,
        frequency_value: Optional[float] = None,
    ):
        self.node_id = node_id
        self.label = label
        self.hsk_level = hsk_level
        self.concreteness = concreteness
        self.frequency_rank = frequency_rank
        self.age_of_acquisition = age_of_acquisition
        self.frequency_value = frequency_value


def load_chinese_word_metadata(kg_file: Path) -> Dict[str, ChineseWordMetadata]:
    """Parse the Chinese KG file and collect metadata for each Chinese word."""
    
    if not kg_file.exists():
        raise FileNotFoundError(f"KG file not found: {kg_file}")
    
    metadata: Dict[str, ChineseWordMetadata] = {}
    current_id: Optional[str] = None
    buffer: Dict[str, Any] = {}
    
    def finalize() -> None:
        nonlocal current_id, buffer
        if current_id and "label" in buffer:
            metadata[current_id] = ChineseWordMetadata(
                node_id=current_id,
                label=str(buffer.get("label", current_id)),
                hsk_level=int(buffer["hsk_level"]) if "hsk_level" in buffer else None,
                concreteness=float(buffer["concreteness"]) if "concreteness" in buffer else None,
                frequency_rank=int(buffer["frequency_rank"]) if "frequency_rank" in buffer else None,
                age_of_acquisition=float(buffer["aoa"]) if "aoa" in buffer else None,
                frequency_value=float(buffer["frequency_value"]) if "frequency_value" in buffer else None,
            )
        current_id = None
        buffer = {}
    
    with kg_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                finalize()
                continue
            
            # Chinese words use "word-" prefix (not "word-en-")
            if line.startswith("srs-kg:word-") and "a srs-kg:Word" in line:
                finalize()
                current_id = line.split()[0].replace("srs-kg:", "")
                buffer = {}
                continue
            
            if not current_id:
                continue
            
            # Chinese label (can be @zh or no language tag)
            if line.startswith("rdfs:label"):
                # Match Chinese labels: "中文"@zh or "中文"
                match = re.search(r'"([^"]+)"(?:@zh)?', line)
                if match:
                    label_text = match.group(1)
                    # Only use if it contains Chinese characters
                    if any('\u4e00' <= c <= '\u9fff' for c in label_text):
                        buffer["label"] = label_text
                continue
            
            # HSK level (instead of CEFR)
            if line.startswith("srs-kg:hskLevel"):
                match = re.search(r"(\d+)", line)
                if match:
                    buffer["hsk_level"] = match.group(1)
                continue
            
            # Concreteness
            if line.startswith("srs-kg:concreteness"):
                match = re.search(r"([\d\.]+)", line)
                if match:
                    buffer["concreteness"] = match.group(1)
                continue
            
            # Frequency (stored as frequency, need to convert to rank)
            if line.startswith("srs-kg:frequency"):
                match = re.search(r"([\d\.]+)", line)
                if match:
                    buffer["frequency_value"] = match.group(1)
                continue
            
            # Frequency rank (if available)
            if line.startswith("srs-kg:frequencyRank"):
                match = re.search(r"(\d+)", line)
                if match:
                    buffer["frequency_rank"] = match.group(1)
                continue
            
            # Age of Acquisition
            if line.startswith("srs-kg:ageOfAcquisition"):
                match = re.search(r"([\d\.]+)", line)
                if match:
                    buffer["aoa"] = match.group(1)
                continue
            
            if line.endswith("."):
                finalize()
    
    finalize()

    # If frequency rank missing but frequency values available, derive ranks
    frequency_entries = [
        meta for meta in metadata.values()
        if meta.frequency_rank is None and meta.frequency_value is not None
    ]
    if frequency_entries:
        frequency_entries.sort(key=lambda m: m.frequency_value, reverse=True)
        for idx, meta in enumerate(frequency_entries, 1):
            meta.frequency_rank = idx

    return metadata


def build_chinese_label_index(metadata: Dict[str, ChineseWordMetadata]) -> Dict[str, str]:
    """Create lookup for Chinese label -> node id."""
    index: Dict[str, str] = {}
    
    for node_id, meta in metadata.items():
        if meta.label:
            # Normalize: strip spaces, lowercase (though Chinese doesn't have case)
            normalized = meta.label.strip()
            if normalized:
                index[normalized] = node_id
                # Also add without spaces for compound words
                no_spaces = normalized.replace(" ", "")
                if no_spaces != normalized:
                    index[no_spaces] = node_id
    
    return index


class ChinesePPRRecommenderService:
    """Service for PPR-based Chinese word recommendations."""
    
    def __init__(
        self,
        similarity_file: Path,
        kg_endpoint: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Chinese PPR recommender service.
        
        Args:
            similarity_file: Path to chinese_word_similarity.json
            kg_endpoint: Optional Fuseki endpoint (if None, uses TTL file)
            config: Configuration dictionary (see DEFAULT_CONFIG)
        """
        self.similarity_file = Path(similarity_file)
        self.kg_endpoint = kg_endpoint
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        
        # Load similarity graph
        print(f"📊 Loading Chinese similarity graph from {self.similarity_file}...")
        self.graph, self.labels = load_similarity_graph(
            self.similarity_file, 
            min_similarity=self.config["min_similarity"]
        )
        print(f"   ✅ Loaded {self.graph.number_of_nodes():,} nodes, {self.graph.number_of_edges():,} edges")
        
        # Chinese doesn't have spelling variants, so variant_to_canonical is empty
        self.variant_to_canonical: Dict[str, str] = {}
        
        # Word metadata and label index will be loaded on demand
        self.word_metadata: Optional[Dict[str, ChineseWordMetadata]] = None
        self.label_index: Optional[Dict[str, str]] = None
    
    def load_kg_metadata(self, kg_file: Optional[Path] = None) -> None:
        """Load Chinese word metadata from KG file or Fuseki."""
        # Always reload if kg_file is provided (to pick up updates)
        if self.word_metadata is not None and kg_file is None:
            return  # Already loaded and no new file provided
        
        if kg_file:
            print(f"📚 Loading Chinese word metadata from {kg_file}...")
            self.word_metadata = load_chinese_word_metadata(kg_file)
            self.label_index = build_chinese_label_index(self.word_metadata)
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
        Map mastered Chinese word texts to KG node IDs.
        
        Returns:
            (matched_ids, unmatched_words)
        """
        if self.label_index is None:
            raise RuntimeError("KG metadata not loaded. Call load_kg_metadata first.")
        
        matched: List[str] = []
        unmatched: List[str] = []
        
        for word in mastered_words:
            # Try direct lookup
            node_id = self.label_index.get(word.strip())
            if not node_id:
                # Try without spaces
                node_id = self.label_index.get(word.strip().replace(" ", ""))
            
            if node_id:
                # For Chinese, node IDs are already normalized (no spelling variants)
                matched.append(node_id)
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
        Get PPR-based Chinese word recommendations.
        
        Args:
            mastered_words: List of mastered Chinese word texts
            profile_id: Optional profile ID (for logging)
            exclude_words: Optional list of words to exclude
            **override_config: Configuration overrides
        
        Returns:
            List of recommendation dictionaries
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
        all_ppr_scores = [s for s in scores.values() if s > 0]
        ppr_mean = math.log10(sum(all_ppr_scores) / len(all_ppr_scores)) if all_ppr_scores else 0.0
        ppr_std = math.sqrt(sum((math.log10(s) - ppr_mean)**2 for s in all_ppr_scores) / len(all_ppr_scores)) if len(all_ppr_scores) > 1 else 1.0
        
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
        
        # Calculate frequency statistics for normalization
        all_freq_ranks = [
            -math.log10(meta.frequency_rank + 1)
            for meta in self.word_metadata.values()
            if meta.frequency_rank is not None and meta.frequency_rank > 0
        ]
        all_freq_values = [
            math.log10(meta.frequency_value + 1)
            for meta in self.word_metadata.values()
            if meta.frequency_value is not None and meta.frequency_value > 0
        ]
        all_freq_transformed = all_freq_ranks + all_freq_values
        freq_mean = sum(all_freq_transformed) / len(all_freq_transformed) if all_freq_transformed else 0.0
        freq_std = (
            math.sqrt(
                sum((f - freq_mean) ** 2 for f in all_freq_transformed) / len(all_freq_transformed)
            )
            if len(all_freq_transformed) > 1
            else 1.0
        )
        
        def transform_ppr(raw_ppr: float) -> float:
            return (math.log10(raw_ppr + 1e-10) - ppr_mean) / ppr_std if ppr_std > 0 else 0.0
        
        def transform_concreteness(value: Optional[float]) -> float:
            if value is None:
                return 0.0
            return (value - conc_mean) / conc_std if conc_std > 0 else 0.0
        
        def transform_frequency(rank: Optional[int], freq_value: Optional[float]) -> float:
            if rank and rank > 0:
                raw = -math.log10(rank + 1)
                # Normalize: higher frequency (lower rank) should give positive boost
                return (raw - freq_mean) / freq_std if freq_std > 0 else 0.0
            if freq_value and freq_value > 0:
                raw = math.log10(freq_value + 1)
                # Normalize: higher frequency should give positive boost
                return (raw - freq_mean) / freq_std if freq_std > 0 else 0.0
            # Missing frequency: use mean (neutral) instead of 0 to avoid penalizing
            return 0.0
        
        def calculate_aoa_penalty(aoa: Optional[float], mental_age: Optional[float]) -> float:
            if aoa is None or mental_age is None:
                return 0.0
            return max(0.0, aoa - mental_age)
        
        # Build excluded node IDs
        excluded_node_ids = set()
        if exclude_words:
            for word in exclude_words:
                node_id = self.label_index.get(word.strip()) or self.label_index.get(word.strip().replace(" ", ""))
                if node_id:
                    excluded_node_ids.add(node_id)
        
        mental_age = config.get("mental_age")
        aoa_buffer = config.get("aoa_buffer", 0.0)
        max_hsk_level = config.get("max_hsk_level")
        words_filtered_by_hsk = 0
        words_with_aoa = 0
        words_filtered_by_aoa = 0
        aoa_penalties_applied = []
        
        candidates = []
        for node_id, raw_ppr_score in scores.items():
            # For Chinese, node IDs are already normalized
            if node_id in seed_weights:
                continue
            if node_id in excluded_node_ids:
                continue
            
            meta = self.word_metadata.get(node_id)
            if not meta:
                continue
            
            # Filter by HSK level if configured
            if (
                max_hsk_level is not None
                and meta.hsk_level is not None
                and meta.hsk_level > max_hsk_level
            ):
                words_filtered_by_hsk += 1
                continue

            # Exclude multi-word if configured
            if config.get("exclude_multiword") and (" " in meta.label or "-" in meta.label):
                continue
            
            # Filter by AoA if mental age is set
            if (
                mental_age is not None
                and meta.age_of_acquisition is not None
            ):
                words_with_aoa += 1
                if meta.age_of_acquisition > mental_age + aoa_buffer:
                    words_filtered_by_aoa += 1
                    continue
                # Calculate penalty
                penalty = calculate_aoa_penalty(meta.age_of_acquisition, mental_age)
                if penalty > 0:
                    aoa_penalties_applied.append(penalty)
            else:
                penalty = 0.0
            
            # Transformed features
            ppr_transformed = transform_ppr(raw_ppr_score)
            conc_transformed = transform_concreteness(meta.concreteness)
            freq_transformed = transform_frequency(meta.frequency_rank, meta.frequency_value)
            aoa_penalty = penalty
            
            # Logit score
            z = (
                config.get("beta_intercept", 0.0)
                + config.get("beta_ppr", 1.0) * ppr_transformed
                + config.get("beta_concreteness", 0.8) * conc_transformed
                + config.get("beta_frequency", 0.3) * freq_transformed
                - config.get("beta_aoa_penalty", 2.0) * aoa_penalty
            )
            
            # Convert to probability using sigmoid
            final_score = 1 / (1 + math.exp(-z))
            
            label = meta.label or self.labels.get(node_id, node_id)
            candidates.append({
                "word": label,
                "node_id": node_id,
                "score": final_score,
                "log_ppr": ppr_transformed,
                "z_concreteness": conc_transformed,
                "log_frequency": freq_transformed,
                "aoa_penalty": aoa_penalty,
                "hsk_level": meta.hsk_level,
                "concreteness": meta.concreteness,
                "frequency_rank": meta.frequency_rank,
                "age_of_acquisition": meta.age_of_acquisition,
            })
        
        # Log frequency statistics
        words_with_freq = sum(1 for c in candidates if c.get('frequency_rank') is not None or c.get('log_frequency', 0) != 0.0)
        print(f"   📊 Frequency data: {words_with_freq}/{len(candidates)} words have frequency data")
        if words_with_freq > 0:
            sample_with_freq = [c for c in candidates[:5] if c.get('frequency_rank') is not None]
            if sample_with_freq:
                print(f"   📊 Sample frequency data: {sample_with_freq[0].get('word')} - rank={sample_with_freq[0].get('frequency_rank')}, log_freq={sample_with_freq[0].get('log_frequency', 0):.2f}")
        
        # Log AoA statistics
        if mental_age is not None:
            print(f"   🧠 Mental age: {mental_age}, AoA buffer: {aoa_buffer}")
            print(f"   📊 Words with AoA data: {words_with_aoa}/{len(candidates) + words_filtered_by_aoa}")
            print(f"   🚫 Words filtered by AoA: {words_filtered_by_aoa}")
            if aoa_penalties_applied:
                avg_penalty = sum(aoa_penalties_applied) / len(aoa_penalties_applied)
                max_penalty = max(aoa_penalties_applied)
                print(f"   ⚠️  AoA penalties applied: {len(aoa_penalties_applied)} words, avg={avg_penalty:.2f}, max={max_penalty:.2f}")

        if max_hsk_level is not None:
            print(f"   📘 Max HSK level: {max_hsk_level} (filtered {words_filtered_by_hsk} words above this level)")
        
        # Sort by score
        candidates.sort(key=lambda item: item["score"], reverse=True)
        
        return candidates[:config.get("top_n", 50)]


# Global service instance (lazy-loaded)
_chinese_service_instance: Optional[ChinesePPRRecommenderService] = None


def get_chinese_ppr_service(
    similarity_file: Optional[Path] = None,
    kg_file: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ChinesePPRRecommenderService:
    """Get or create global Chinese PPR service instance."""
    global _chinese_service_instance
    
    if similarity_file is None:
        similarity_file = PROJECT_ROOT / "data" / "content_db" / "chinese_word_similarity.json"
    if kg_file is None:
        # Use merged KG to ensure AoA/frequency metadata is available
        kg_file = PROJECT_ROOT / "knowledge_graph" / "world_model_merged.ttl"
    
    # Ensure paths are absolute
    similarity_file = similarity_file.resolve()
    kg_file = kg_file.resolve()
    
    # Check if files exist
    if not similarity_file.exists():
        raise FileNotFoundError(f"Similarity file not found: {similarity_file}")
    if not kg_file.exists():
        raise FileNotFoundError(f"KG file not found: {kg_file}")
    
    # Check if we need to recreate the instance (if kg_file changed or instance doesn't exist)
    # If kg_file is explicitly provided and different from cached, reset the instance
    # Also check file modification time to detect updates
    should_reset = False
    if _chinese_service_instance is None:
        # No instance exists, create new one
        pass
    elif not hasattr(_chinese_service_instance, '_kg_file'):
        # Instance exists but doesn't have _kg_file attribute (old instance), reset it
        should_reset = True
    elif _chinese_service_instance._kg_file != kg_file:
        # Instance exists but kg_file changed, reset it
        should_reset = True
    elif hasattr(_chinese_service_instance, '_kg_file_mtime'):
        # Check if file modification time changed (file was updated)
        try:
            current_mtime = kg_file.stat().st_mtime
            if current_mtime != _chinese_service_instance._kg_file_mtime:
                should_reset = True
        except (OSError, AttributeError):
            pass
    
    if should_reset:
        _chinese_service_instance = None
    
    if _chinese_service_instance is None:
        try:
            _chinese_service_instance = ChinesePPRRecommenderService(
                similarity_file=similarity_file,
                config=config
            )
            _chinese_service_instance.load_kg_metadata(kg_file=kg_file)
            # Store the kg_file path and modification time so we can detect changes
            _chinese_service_instance._kg_file = kg_file
            try:
                _chinese_service_instance._kg_file_mtime = kg_file.stat().st_mtime
            except (OSError, AttributeError):
                _chinese_service_instance._kg_file_mtime = None
        except Exception as e:
            # Reset instance on error so it can be retried
            _chinese_service_instance = None
            raise RuntimeError(f"Failed to initialize Chinese PPR service: {str(e)}") from e
    
    return _chinese_service_instance

