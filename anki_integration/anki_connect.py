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
            filename = f"srs4autism_{content_hash}.{img_type}"
            
            try:
                # Store the file in Anki's media folder
                self.store_media_file(filename, img_data)
                
                # Return img tag with media reference
                return f'<img src="{filename}">'
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
                 tags: List[str] = None) -> int:
        """
        Add a note to Anki.
        
        Args:
            deck_name: Target deck name
            model_name: Note type (e.g., "Basic", "Cloze")
            fields: Dictionary of field names to values
            tags: List of tags to add
            
        Returns:
            Note ID
        """
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": fields,
            "tags": tags or []
        }
        
        return self._invoke("addNote", {"note": note})
    
    def add_basic_card(self, deck_name: str, front: str, back: str, 
                      tags: List[str] = None) -> int:
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
        return self.add_note(
            deck_name=deck_name,
            model_name="Basic",
            fields={"Front": front, "Back": back},
            tags=tags
        )
    
    def add_basic_reverse_card(self, deck_name: str, front: str, back: str,
                              tags: List[str] = None) -> int:
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
        return self.add_note(
            deck_name=deck_name,
            model_name="Basic (and reversed card)",
            fields={"Front": front, "Back": back},
            tags=tags
        )
    
    def add_cloze_card(self, deck_name: str, text: str, extra: str = "",
                      tags: List[str] = None) -> int:
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
        return self.add_note(
            deck_name=deck_name,
            model_name="Cloze",
            fields={"Text": text, "Extra": extra},
            tags=tags
        )
    
    def add_custom_note(self, deck_name: str, note_type: str, fields: Dict[str, str],
                       tags: List[str] = None) -> int:
        """
        Add a note with custom note type and fields.
        
        Args:
            deck_name: Target deck name
            note_type: Custom note type name (e.g., "Interactive Cloze")
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
                tags = card.get("tags", [])
                cloze_text = card.get("cloze_text")
                text_field = card.get("text_field")
                extra_field = card.get("extra_field", "")
                note_type = card.get("note_type")
                
                print(f"  Processing card {card.get('id')}: type={card_type}, note_type={note_type}")
                
                # Handle custom note types
                if note_type:
                    # Custom note type with custom fields
                    fields = {}
                    if text_field:
                        # Process images in text field
                        processed_text = self._process_html_images(text_field)
                        fields["Text"] = processed_text
                        print(f"    Text field length: {len(text_field)} chars (original), {len(processed_text)} chars (processed)")
                    if extra_field:
                        # Process images in extra field
                        processed_extra = self._process_html_images(extra_field)
                        fields["Extra"] = processed_extra
                        print(f"    Extra field length: {len(extra_field)} chars (original), {len(processed_extra)} chars (processed)")
                    # Add any other custom fields from the card
                    for key, value in card.items():
                        if key.startswith("field_"):
                            field_name = key.replace("field_", "")
                            fields[field_name] = value
                    
                    print(f"    Adding custom note: {note_type} with fields: {list(fields.keys())}")
                    note_id = self.add_custom_note(deck_name, note_type, fields, tags)
                    print(f"    ✅ Created note ID: {note_id}")
                
                # Handle standard card types
                elif card_type == "cloze" and cloze_text:
                    # Process images in cloze text
                    processed_cloze = self._process_html_images(cloze_text)
                    note_id = self.add_cloze_card(deck_name, processed_cloze, "", tags)
                elif card_type == "basic_reverse":
                    # Process images in front and back
                    processed_front = self._process_html_images(front)
                    processed_back = self._process_html_images(back)
                    note_id = self.add_basic_reverse_card(deck_name, processed_front, processed_back, tags)
                else:  # basic
                    # Process images in front and back
                    processed_front = self._process_html_images(front)
                    processed_back = self._process_html_images(back)
                    note_id = self.add_basic_card(deck_name, processed_front, processed_back, tags)
                
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

