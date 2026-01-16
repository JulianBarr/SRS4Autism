import json
import os
import re
import unicodedata
from typing import Any, List, Dict, Optional, Tuple, Union, Set

TAG_ANNOTATION_PREFIXES = (
    "pronunciation",
    "meaning",
    "hsk",
    "knowledge",
    "note",
    "remark",
    "example",
)

CHINESE_CHAR_PATTERN = re.compile(r'[\u4e00-\u9fff]')

def load_json_file(file_path: str, default: Any = None) -> Any:
    """Load JSON data from file, return default if file doesn't exist"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default if default is not None else []
    return default if default is not None else []

def save_json_file(file_path: str, data: Any):
    """Save data to JSON file"""
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

def normalize_to_slug(value: str) -> str:
    """Normalize a string to a slug-friendly format without enforcing uniqueness."""
    if not value:
        return ""
    slug = value.lower()
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'[^\w\u4e00-\u9fff-]', '', slug)
    slug = slug.strip('-')
    slug = re.sub(r'-+', '-', slug)
    return slug

def normalize_for_kp_id(value: str) -> str:
    """Normalize text for inclusion in a knowledge point identifier."""
    if value is None:
        return ""
    value = str(value).strip()
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = ''.join(ch for ch in value if not unicodedata.combining(ch))
    for sep in [' ', '/', '\\', ':', '@', ',', '，', ';', '；', '|']:
        value = value.replace(sep, '-')
    value = re.sub(r'-+', '-', value)
    slug = normalize_to_slug(value)
    return slug or "value"

def generate_kp_id(subject: str, predicate: str, obj: str) -> str:
    """Create a composite knowledge point identifier."""
    subject_part = normalize_for_kp_id(subject) or "subject"
    predicate_part = normalize_for_kp_id(predicate) or "predicate"
    object_part = normalize_for_kp_id(obj) or "value"
    return f"kp:{subject_part}--{predicate_part}--{object_part}"

def contains_chinese_chars(value: str) -> bool:
    """Check if the string contains any Chinese characters."""
    if not value:
        return False
    return bool(CHINESE_CHAR_PATTERN.search(value))

def split_tag_annotations(tags: Union[List[Any], str, None]) -> Tuple[List[str], List[str]]:
    """Separate descriptive annotations from machine-friendly tags."""
    clean_tags: List[str] = []
    annotations: List[str] = []
    
    # Handle case where tags is a string (comma-separated or single tag)
    if isinstance(tags, str):
        # Split comma-separated string into list
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    elif not isinstance(tags, (list, tuple)):
        # If it's not a string or list, convert to list
        tags = [tags] if tags else []
    
    for tag in tags or []:
        if tag is None:
            continue
        tag_str = str(tag).strip()
        if not tag_str:
            continue
        lowered = tag_str.lower()
        if ":" in tag_str or any(lowered.startswith(prefix) for prefix in TAG_ANNOTATION_PREFIXES):
            annotations.append(tag_str)
        else:
            clean_tags.append(tag_str)
    return clean_tags, annotations

def build_cuma_remarks(card: Dict[str, Any], context_tags: List[Dict[str, Any]]) -> str:
    """Construct the _Remarks field combining tags and knowledge point info."""
    lines: List[str] = []
    original_tags = card.get("tags", []) or []
    clean_tags, extracted_annotations = split_tag_annotations(original_tags)
    card["tags"] = clean_tags
    annotations = (card.get("field__Remarks_annotations") or []) + extracted_annotations
    kp_ids_set: Set[str] = set(card.get("knowledge_points") or [])
    knowledge_entries: List[str] = []
    knowledge_entries_seen: Set[str] = set()

    def add_entry(text: str):
        if not text:
            return
        formatted = text.strip()
        if not formatted:
            return
        if formatted not in knowledge_entries_seen:
            knowledge_entries.append(formatted)
            knowledge_entries_seen.add(formatted)

    def add_kp_entry(raw_kp: str):
        kp_value = (raw_kp or "").strip()
        if not kp_value:
            return
        # Ensure it has kp: prefix for storage
        if not kp_value.startswith("kp:"):
            stored_kp = f"kp:{kp_value}"
        else:
            stored_kp = kp_value
        kp_ids_set.add(stored_kp)
        
        # Parse the KP for readable display
        display_parts = kp_value.split("--", 2) if not kp_value.startswith("kp:") else kp_value[3:].split("--", 2)
        if len(display_parts) == 3:
            subj, pred, obj = display_parts
            # Create readable display format based on predicate
            pred_lower = pred.lower().replace('-', ' ')
            if pred_lower in ['means', 'has meaning', 'meaning']:
                # "读者 means reader (concept)"
                display_text = f"{subj} means {obj} (concept)"
            elif pred_lower in ['has pronunciation', 'pronunciation', 'pronounced']:
                # "读者 pronounced dú zhě"
                display_text = f"{subj} pronounced {obj}"
            elif pred_lower in ['has hsk level', 'hsk level', 'hsk']:
                # "读者 HSK level 3"
                display_text = f"{subj} HSK level {obj}"
            elif pred_lower in ['has grammar rule', 'grammar rule', 'grammar']:
                # "把 grammar rule: causative construction"
                display_text = f"{subj} grammar rule: {obj}"
            elif pred_lower in ['has part of speech', 'part of speech', 'pos']:
                # "读者 part of speech: noun"
                display_text = f"{subj} part of speech: {obj}"
            else:
                # Generic format: "subject → object (predicate)"
                display_text = f"{subj} → {obj} ({pred.replace('-', ' ')})"
        else:
            # Fallback to raw format if parsing fails
            display_text = kp_value.replace("kp:", "").replace("--", " → ")
        add_entry(display_text)

    # Seed knowledge points from card metadata
    for kp in sorted(kp_ids_set):
        add_kp_entry(kp)

    # Allow explicit @kp:... mentions to append
    for tag in context_tags or []:
        if tag.get("type") == "kp":
            value = (tag.get("value") or "").strip()
            if value:
                if not value.startswith("kp:"):
                    value = f"kp:{value}"
                add_kp_entry(value)
    
    for annotation in annotations:
        annotation_text = str(annotation).strip()
        if not annotation_text:
            continue
        if annotation_text.startswith("kp:"):
            add_kp_entry(annotation_text)
        else:
            add_entry(annotation_text)
    
    if knowledge_entries:
        lines.append("Knowledge Points:")
        for entry in knowledge_entries:
            lines.append(f"- {entry}")
    
    if clean_tags:
        lines.append("CUMA Tags: " + ", ".join(clean_tags))

    if kp_ids_set:
        card["knowledge_points"] = sorted(kp_ids_set)
    else:
        card.pop("knowledge_points", None)
    
    return "\n".join(lines).strip()
