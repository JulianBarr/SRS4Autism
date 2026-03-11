"""
AnkiConnect Integration for SRS4Autism

This module provides a Python interface to communicate with Anki via AnkiConnect add-on.
AnkiConnect must be installed in Anki for this to work.

Installation: https://ankiweb.net/shared/info/2055492159
"""

import requests
import json
import re
import base64
import hashlib
from typing import List, Dict, Any, Optional


TAG_ANNOTATION_PREFIXES = (
    "pronunciation",
    "meaning",
    "hsk",
    "knowledge",
    "note",
    "remark",
    "example",
)


def sanitize_tags_for_anki(raw_tags: List[Any]) -> List[str]:
    """Return an empty tag list so that metadata lives in _Remarks instead of Anki tags."""
    return []


class AnkiConnect:
    """Client for communicating with Anki via AnkiConnect API."""
    
    def __init__(self, url: str = "http://localhost:8765"):
        """
        Initialize AnkiConnect client.
        
        Args:
            url: AnkiConnect server URL (default: http://localhost:8765)
        """
        self.url = url
        self.version = 6
    
    def _invoke(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Invoke an AnkiConnect action.
        
        Args:
            action: The AnkiConnect action to invoke
            params: Parameters for the action
            
        Returns:
            The result from AnkiConnect
            
        Raises:
            Exception: If AnkiConnect returns an error
        """
        payload = {
            "action": action,
            "version": self.version
        }
        
        if params:
            payload["params"] = params
        
        try:
            response = requests.post(self.url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("error"):
                raise Exception(f"AnkiConnect error: {result['error']}")
            
            return result.get("result")
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to connect to AnkiConnect: {e}")
    
    def ping(self) -> bool:
        """
        Check if AnkiConnect is running and accessible.
        
        Returns:
            True if AnkiConnect is accessible
        """
        try:
            self._invoke("version")
            return True
        except:
            return False
    
    def get_deck_names(self) -> List[str]:
        """Get list of all deck names."""
        return self._invoke("deckNames")
    
    def store_media_file(self, filename: str, data: str) -> str:
        """
        Store a media file in Anki's media folder.
        
        Args:
            filename: Name of the file
            data: Base64-encoded file data
            
        Returns:
            The filename as stored in Anki
        """
        return self._invoke("storeMediaFile", {
            "filename": filename,
            "data": data
        })
    
    def _process_html_images(self, html: str) -> str:
        """
        Convert base64 embedded images to Anki media references.
        
        Args:
            html: HTML content with embedded base64 images
            
        Returns:
            HTML with media file references instead of base64
        """
        if not html:
            return html
        
        # Find all base64 image tags
        pattern = r'<img[^>]*src="data:image/([^;]+);base64,([^"]+)"[^>]*>'
        
        def replace_image(match):
            img_type = match.group(1)  # png, jpeg, etc.
            img_data = match.group(2)  # base64 data
            
            # Generate a unique filename based on content hash
            content_hash = hashlib.md5(img_data.encode()).hexdigest()[:12]
            filename = f"{content_hash}.{img_type}"
            
            try:
                # Store the file in Anki's media folder
                self.store_media_file(filename, img_data)
                
                # Return img tag with media reference
                return f'<img src="/static/media/{filename}">'
            except Exception as e:
                print(f"Warning: Failed to store image {filename}: {e}")
                # If storing fails, keep original (but this might still cause issues)
                return match.group(0)
        
        # Replace all base64 images with media references
        processed_html = re.sub(pattern, replace_image, html)
        
        return processed_html
    
    def create_deck(self, deck_name: str) -> int:
        """
        Create a new deck.
        
        Args:
            deck_name: Name of the deck to create
            
        Returns:
            Deck ID
        """
        return self._invoke("createDeck", {"deck": deck_name})
    
    def add_note(self, deck_name: str, model_name: str, fields: Dict[str, str], 
                 tags: List[str] = None, allow_duplicate: bool = True) -> int:
        """
        Add a note to Anki.
        
        Args:
            deck_name: Target deck name
            model_name: Note type (e.g., "Basic", "Cloze")
            fields: Dictionary of field names to values
            tags: List of tags to add
            allow_duplicate: If True, allows creating duplicate notes (default: True)
            
        Returns:
            Note ID
        """
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": fields,
            "tags": tags or [],
            "options": {
                "allowDuplicate": allow_duplicate
            }
        }
        
        return self._invoke("addNote", {"note": note})
    
    def add_basic_card(self, deck_name: str, front: str, back: str, 
                      tags: List[str] = None, remarks: str = "") -> int:
        """
        Add a basic flashcard.
        
        Args:
            deck_name: Target deck name
            front: Front of the card
            back: Back of the card
            tags: List of tags
            
        Returns:
            Note ID
        """
        fields = {"Front": front, "Back": back}
        if remarks is not None:
            fields["_Remarks"] = remarks
        return self.add_note(
            deck_name=deck_name,
            model_name="CUMA - Basic",
            fields=fields,
            tags=sanitize_tags_for_anki(tags)
        )
    
    def add_basic_reverse_card(self, deck_name: str, front: str, back: str,
                              tags: List[str] = None, remarks: str = "") -> int:
        """
        Add a basic reverse flashcard (card that works both ways).
        
        Args:
            deck_name: Target deck name
            front: Front of the card
            back: Back of the card
            tags: List of tags
            
        Returns:
            Note ID
        """
        fields = {"Front": front, "Back": back}
        if remarks is not None:
            fields["_Remarks"] = remarks
        return self.add_note(
            deck_name=deck_name,
            model_name="CUMA - Basic (and reversed card)",
            fields=fields,
            tags=sanitize_tags_for_anki(tags)
        )
    
    def add_cloze_card(self, deck_name: str, text: str, extra: str = "",
                      tags: List[str] = None, remarks: str = "") -> int:
        """
        Add a cloze deletion card.
        
        Args:
            deck_name: Target deck name
            text: Text with cloze deletions (e.g., "The {{c1::answer}} is here")
            extra: Extra information (optional)
            tags: List of tags
            
        Returns:
            Note ID
        """
        fields = {"Text": text, "Extra": extra}
        if remarks is not None:
            fields["_Remarks"] = remarks
        return self.add_note(
            deck_name=deck_name,
            model_name="CUMA - Cloze",
            fields=fields,
            tags=sanitize_tags_for_anki(tags)
        )
    
    def add_custom_note(self, deck_name: str, note_type: str, fields: Dict[str, str],
                       tags: List[str] = None) -> int:
        """
        Add a note with custom note type and fields.
        
        Args:
            deck_name: Target deck name
            note_type: Custom note type name (e.g., "CUMA - Interactive Cloze")
            fields: Dictionary of field names to values
            tags: List of tags
            
        Returns:
            Note ID
        """
        return self.add_note(
            deck_name=deck_name,
            model_name=note_type,
            fields=fields,
            tags=tags
        )

    def add_notes(
        self,
        notes: List[Dict[str, Any]],
        allow_duplicate: bool = False,
    ) -> List[Optional[int]]:
        """
        Add multiple notes to Anki in one batch (AnkiConnect addNotes action).

        Args:
            notes: List of note dicts, each with deckName, modelName, fields, optional tags
            allow_duplicate: If True, allows creating duplicate notes

        Returns:
            List of note IDs (or None for notes that failed/duplicate)
        """
        payload_notes = []
        for n in notes:
            note = {
                "deckName": n["deckName"],
                "modelName": n["modelName"],
                "fields": n["fields"],
                "tags": n.get("tags", []),
                "options": {"allowDuplicate": allow_duplicate},
            }
            payload_notes.append(note)
        return self._invoke("addNotes", {"notes": payload_notes})

    def push_grouped_examples_to_anki(
        self,
        examples: List[Dict[str, Any]],
        deck_name: str = "CUMA_Test_Lab",
        model_name: str = "CUMA - Grouped Interactive Cloze",
        allow_duplicate: bool = False,
    ) -> Dict[str, Any]:
        """
        Push generated vocabulary/grammar examples to Anki using the Grouped Interactive Cloze note type.

        Groups examples by target_word (or knowledge_point) so each Note contains ONLY
        examples testing the SAME knowledge point. SRS best practice: siblings must share
        the exact same target to enable Anki's "bury related cards" correctly.

        Args:
            examples: List of dicts with keys: front, back; and at least one of:
                target_word, knowledge_point. Optional: remarks, source_url, kg_map.
            deck_name: Target deck (default: CUMA_Test_Lab for sandbox testing)
            model_name: Note type (default: CUMA - Grouped Interactive Cloze)
            allow_duplicate: Whether to allow duplicate notes

        Returns:
            Dict with note_ids, success_count, failed_count, errors
        """
        if not examples:
            return {"note_ids": [], "success_count": 0, "failed_count": 0, "errors": []}

        # Helper: extract target word from Anki cloze [[c1::target]] in front text
        _CLOZE_RE = re.compile(r"\[\[c1::([^\]]+)\]\]")

        def _group_key(ex: dict) -> str:
            """SRS-critical: each Note must group by the SAME target word."""
            tw = ex.get("target_word") or ex.get("targetWord") or ""
            if tw:
                return str(tw).strip()
            kp = ex.get("knowledge_point") or ""
            if kp and kp != "General":
                return str(kp).strip()
            front = ex.get("front", "")
            m = _CLOZE_RE.search(front)
            if m:
                return m.group(1).strip()
            return kp or "General"

        # 1. Group by target word (SRS: siblings must share same knowledge point)
        from itertools import groupby

        sorted_examples = sorted(examples, key=_group_key)
        grouped = {
            k: list(grp)
            for k, grp in groupby(sorted_examples, key=_group_key)
        }

        # 2. Chunk into batches of 5 per target word (each chunk = one Note)
        def _chunk_list(lst: List, size: int):
            for i in range(0, len(lst), size):
                yield lst[i : i + size]

        notes_to_add = []
        for target_key, ex_list in grouped.items():
            for chunk in _chunk_list(ex_list, 5):
                # 3. Initialize fields
                fields = {
                    f"Text{i}": "" for i in range(1, 6)
                }
                fields.update({f"Extra{i}": "" for i in range(1, 6)})

                # 4. Format and map each example in the chunk (all same target_word)
                for i, ex in enumerate(chunk, start=1):
                    front = ex.get("front", "")
                    back = ex.get("back", "")
                    # Pass front through as-is; CUMA pipeline already has [[c1::target]] cloze syntax
                    fields[f"Text{i}"] = front
                    fields[f"Extra{i}"] = back

                # 4b. Add metadata fields (_Remarks, _KG_Map) for production CUMA compatibility
                # Use first example's metadata or sensible defaults
                first_ex = chunk[0] if chunk else {}
                # Avoid printing "General" on the card; use generic label for fallback
                remarks = first_ex.get("remarks") or first_ex.get("source_url") or (
                    f"CUMA - {target_key}" if target_key and target_key != "General" else "CUMA"
                )
                kg_map = first_ex.get("kg_map") or ""
                fields["_Remarks"] = remarks
                fields["_KG_Map"] = kg_map

                notes_to_add.append(
                    {
                        "deckName": deck_name,
                        "modelName": model_name,
                        "fields": fields,
                        "tags": [],
                        "options": {"allowDuplicate": allow_duplicate},
                    }
                )

        # 5. Ensure deck exists
        try:
            self.create_deck(deck_name)
        except Exception:
            pass  # Deck may already exist

        # 6. Build addNotes payload (flatten options into each note)
        payload_notes = []
        for n in notes_to_add:
            payload_notes.append(
                {
                    "deckName": n["deckName"],
                    "modelName": n["modelName"],
                    "fields": n["fields"],
                    "tags": n.get("tags", []),
                    "options": {"allowDuplicate": allow_duplicate},
                }
            )

        # 7. Invoke addNotes
        try:
            result = self._invoke("addNotes", {"notes": payload_notes})
        except Exception as e:
            return {
                "note_ids": [],
                "success_count": 0,
                "failed_count": len(notes_to_add),
                "errors": [str(e)],
            }

        # 8. Parse result (addNotes returns list of IDs or null for failures)
        note_ids = [x if x is not None else None for x in (result or [])]
        success_count = sum(1 for x in note_ids if x is not None)
        failed_count = len(note_ids) - success_count
        errors = []
        for idx, nid in enumerate(note_ids):
            if nid is None:
                errors.append(f"Note {idx + 1} failed to create (possibly duplicate)")

        return {
            "note_ids": note_ids,
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors,
        }

    def sync_cards(self, deck_name: str, cards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sync multiple cards to Anki.
        
        Args:
            deck_name: Target deck name
            cards: List of card dictionaries with card_type, front, back, etc.
            
        Returns:
            Dictionary with sync results
        """
        results = {
            "success": [],
            "failed": [],
            "total": len(cards)
        }
        
        # Create deck if it doesn't exist
        try:
            self.create_deck(deck_name)
        except:
            pass  # Deck might already exist
        
        for card in cards:
            try:
                card_type = card.get("card_type", "basic")
                front = card.get("front", "")
                back = card.get("back", "")
                tags = sanitize_tags_for_anki(card.get("tags", []))
                cloze_text = card.get("cloze_text")
                text_field = card.get("text_field")
                extra_field = card.get("extra_field", "")
                note_type = card.get("note_type")
                remarks_value = card.get("field__Remarks") or card.get("field__remarks") or ""
                
                print(f"  Processing card {card.get('id')}: type={card_type}, note_type={note_type}")
                print(f"    Debug - text_field: {repr(text_field[:100]) if text_field else 'None'}")
                print(f"    Debug - extra_field: {repr(extra_field[:100]) if extra_field else 'None'}")
                print(f"    Debug - front: {repr(front[:100]) if front else 'None'}")
                print(f"    Debug - back: {repr(back[:100]) if back else 'None'}")
                print(f"    Debug - cloze_text: {repr(cloze_text[:100]) if cloze_text else 'None'}")
                
                # Handle custom note types
                if note_type:
                    # Determine field names based on note type
                    # "CUMA - Basic" and "CUMA - Basic (and reversed card)" use "Front"/"Back"
                    # "CUMA - Cloze", "CUMA - Interactive Cloze", "Interactive Cloze" use "Text"/"Extra"
                    is_basic_type = "Basic" in note_type and "Cloze" not in note_type
                    
                    if is_basic_type:
                        primary_field = "Front"
                        secondary_field = "Back"
                    else:
                        primary_field = "Text"
                        secondary_field = "Extra"
                    
                    print(f"    Field mapping: note_type='{note_type}', is_basic_type={is_basic_type}, primary='{primary_field}', secondary='{secondary_field}'")
                    
                    # Custom note type with custom fields
                    fields = {}
                    
                    # Try text_field first, then fallback to front or cloze_text
                    content_for_primary = None
                    if text_field and text_field.strip():
                        content_for_primary = text_field
                    elif front and front.strip():
                        content_for_primary = front
                    elif cloze_text and cloze_text.strip():
                        content_for_primary = cloze_text
                    
                    if content_for_primary:
                        # Process images in primary field
                        processed_primary = self._process_html_images(content_for_primary)
                        fields[primary_field] = processed_primary
                        print(f"    {primary_field} field length: {len(content_for_primary)} chars (original), {len(processed_primary)} chars (processed)")
                    else:
                        # Ensure primary field exists even if empty (Anki requires all fields)
                        fields[primary_field] = ""
                    
                    # Try extra_field first, then fallback to back
                    content_for_secondary = None
                    if extra_field and extra_field.strip():
                        content_for_secondary = extra_field
                    elif back and back.strip():
                        content_for_secondary = back
                    
                    if content_for_secondary:
                        # Process images in secondary field
                        processed_secondary = self._process_html_images(content_for_secondary)
                        fields[secondary_field] = processed_secondary
                        print(f"    {secondary_field} field length: {len(content_for_secondary)} chars (original), {len(processed_secondary)} chars (processed)")
                    else:
                        # Ensure secondary field exists even if empty (Anki requires all fields)
                        fields[secondary_field] = ""
                    
                    # Add any other custom fields from the card (but don't overwrite primary/secondary fields)
                    for key, value in card.items():
                        if key.startswith("field_"):
                            if key == "field__Remarks_annotations":
                                continue
                            field_name = key.replace("field_", "")
                            # Don't overwrite the primary/secondary fields we just set
                            if field_name in (primary_field, secondary_field):
                                continue
                            # Only add non-empty values
                            if value and (isinstance(value, str) and value.strip() or not isinstance(value, str)):
                                fields[field_name] = str(value) if value else ""
                    if remarks_value and "_Remarks" not in fields:
                        fields["_Remarks"] = remarks_value
                    
                    # Validate that we have at least one non-empty field (Anki rejects completely empty notes)
                    non_empty_fields = {k: v for k, v in fields.items() if v and str(v).strip()}
                    if not non_empty_fields:
                        raise ValueError(
                            f"Card {card.get('id')} has empty fields. "
                            f"text_field: {repr(text_field[:50]) if text_field else 'None'}, "
                            f"extra_field: {repr(extra_field[:50]) if extra_field else 'None'}, "
                            f"front: {repr(front[:50]) if front else 'None'}, "
                            f"back: {repr(back[:50]) if back else 'None'}, "
                            f"cloze_text: {repr(cloze_text[:50]) if cloze_text else 'None'}, "
                            f"note_type: {note_type}, "
                            f"card_type: {card_type}, "
                            f"fields set: {list(fields.keys())}, "
                            f"non_empty: {list(non_empty_fields.keys())}"
                        )
                    
                    print(f"    Adding custom note: {note_type} with fields: {list(fields.keys())} (values: {[(k, len(str(v)) if v else 0) for k, v in fields.items()]})")
                    note_id = self.add_custom_note(deck_name, note_type, fields, tags)
                    print(f"    ✅ Created note ID: {note_id}")
                
                # Handle standard card types
                elif card_type == "cloze" and cloze_text:
                    # Process images in cloze text
                    processed_cloze = self._process_html_images(cloze_text)
                    note_id = self.add_cloze_card(deck_name, processed_cloze, "", tags, remarks_value)
                elif card_type == "basic_reverse":
                    # Process images in front and back
                    processed_front = self._process_html_images(front)
                    processed_back = self._process_html_images(back)
                    note_id = self.add_basic_reverse_card(deck_name, processed_front, processed_back, tags, remarks_value)
                else:  # basic
                    # Process images in front and back
                    processed_front = self._process_html_images(front)
                    processed_back = self._process_html_images(back)
                    note_id = self.add_basic_card(deck_name, processed_front, processed_back, tags, remarks_value)
                
                results["success"].append({
                    "card_id": card.get("id"),
                    "note_id": note_id
                })
            
            except Exception as e:
                print(f"    ❌ Error syncing card {card.get('id')}: {e}")
                results["failed"].append({
                    "card_id": card.get("id"),
                    "error": str(e)
                })
        
        return results


def test_connection() -> bool:
    """
    Test connection to AnkiConnect.
    
    Returns:
        True if connection successful
    """
    client = AnkiConnect()
    return client.ping()


if __name__ == "__main__":
    # Test the connection
    print("Testing AnkiConnect connection...")
    
    client = AnkiConnect()
    
    if client.ping():
        print("✅ Connected to AnkiConnect successfully!")
        print(f"Available decks: {client.get_deck_names()}")
    else:
        print("❌ Failed to connect to AnkiConnect")
        print("Make sure:")
        print("1. Anki is running")
        print("2. AnkiConnect add-on is installed")
        print("3. No firewall is blocking localhost:8765")

