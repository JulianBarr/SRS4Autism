"""
Anki Template Manager - Server-Side Rendering Factory

This module provides a factory pattern for generating Anki card templates
dynamically based on user configuration profiles. Templates are generated
as HTML/CSS strings in Python and pushed to Anki via Anki-Connect.

This approach eliminates complex JavaScript logic inside Anki templates
by generating the exact HTML needed for each configuration profile.
"""

import requests
from typing import Dict, Any, Optional


class AnkiTemplateFactory:
    """
    Factory class for generating Anki card templates based on configuration.
    
    Generates HTML and CSS strings dynamically, allowing features to be
    literally excluded from the HTML source rather than hidden with CSS.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the factory with a configuration dictionary.
        
        Args:
            config: Configuration dictionary with keys:
                - mode: 'verbal' or 'non-verbal'
                - dark_mode: bool (default: False)
                - scaffold_level: 'high' or 'low' (default: 'low')
        """
        self.config = config
        self.mode = config.get('mode', 'verbal')
        self.dark_mode = config.get('dark_mode', False)
        self.scaffold_level = config.get('scaffold_level', 'low')
    
    def _generate_css(self) -> str:
        """
        Generate CSS string based on configuration.
        
        Returns:
            CSS string with dark mode support if enabled
        """
        if self.dark_mode:
            return """
.card {
    font-family: Arial, sans-serif;
    font-size: 24px;
    text-align: center;
    color: #e0e0e0;
    background-color: #1a1a1a;
    padding: 20px;
    min-height: 100vh;
}

.concept {
    font-size: 1.2em;
    font-weight: bold;
    color: #ffffff;
    margin-bottom: 15px;
}

.visual img {
    max-height: 300px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.5);
}

.sentence {
    font-size: 1.4em;
    margin: 20px 0;
    line-height: 1.6;
    color: #e0e0e0;
}

.cloze {
    font-weight: bold;
    color: #64b5f6;
}

.hint {
    font-size: 0.8em;
    color: #f48fb1;
    margin-top: 10px;
    font-style: italic;
}

.type-prompt {
    font-size: 0.8em;
    color: #b0b0b0;
    margin-top: 20px;
}

input {
    font-size: 1.2em;
    text-align: center;
    padding: 5px;
    border: 1px solid #555;
    border-radius: 4px;
    background-color: #2a2a2a;
    color: #e0e0e0;
}

.audio-button {
    width: 200px;
    height: 200px;
    border-radius: 50%;
    background-color: #2196F3;
    color: white;
    font-size: 2em;
    border: none;
    cursor: pointer;
    margin: 20px auto;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
    transition: background-color 0.2s;
}

.audio-button:active {
    background-color: #1976D2;
}

.hint-button {
    font-size: 0.9em;
    padding: 8px 16px;
    background-color: #555;
    color: #e0e0e0;
    border: 1px solid #777;
    border-radius: 4px;
    cursor: pointer;
    margin-top: 10px;
}

.hint-button:hover {
    background-color: #666;
}

/* Hide Anki's native audio player elements */
audio {
    display: none !important;
}

.replay-button {
    display: none !important;
}

.soundLink {
    display: none !important;
}

/* Hidden container for audio (audio is loaded but not visible) */
.audio-hidden {
    display: none !important;
}
"""
        else:
            return """
.card {
    font-family: Arial, sans-serif;
    font-size: 24px;
    text-align: center;
    color: #333;
    background-color: #f9f9f9;
    padding: 20px;
    min-height: 100vh;
}

.concept {
    font-size: 1.2em;
    font-weight: bold;
    color: #555;
    margin-bottom: 15px;
}

.visual img {
    max-height: 300px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.sentence {
    font-size: 1.4em;
    margin: 20px 0;
    line-height: 1.6;
}

.cloze {
    font-weight: bold;
    color: #2196F3;
}

.hint {
    font-size: 0.8em;
    color: #e91e63;
    margin-top: 10px;
    font-style: italic;
}

.type-prompt {
    font-size: 0.8em;
    color: #888;
    margin-top: 20px;
}

input {
    font-size: 1.2em;
    text-align: center;
    padding: 5px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

.audio-button {
    width: 200px;
    height: 200px;
    border-radius: 50%;
    background-color: #2196F3;
    color: white;
    font-size: 2em;
    border: none;
    cursor: pointer;
    margin: 20px auto;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    transition: background-color 0.2s;
}

.audio-button:active {
    background-color: #1976D2;
}

.hint-button {
    font-size: 0.9em;
    padding: 8px 16px;
    background-color: #f0f0f0;
    color: #333;
    border: 1px solid #ddd;
    border-radius: 4px;
    cursor: pointer;
    margin-top: 10px;
}

.hint-button:hover {
    background-color: #e0e0e0;
}

/* Hide Anki's native audio player elements */
audio {
    display: none !important;
}

.replay-button {
    display: none !important;
}

.soundLink {
    display: none !important;
}

/* Hidden container for audio (audio is loaded but not visible) */
.audio-hidden {
    display: none !important;
}
"""
    
    def _generate_front(self) -> str:
        """
        Generate Front Template HTML based on configuration.
        
        Logic:
        - Verbal Mode: Includes typing field {{type:Pinyin_Clean}}
        - Non-Verbal Mode: Large touch-friendly audio button (no typing)
        - Scaffolding: High = show Sentence_Cloze, Low = hide or hint button
        
        Returns:
            Front template HTML string
        """
        html_parts = ['<div class="card">']
        
        # Concept (always shown)
        html_parts.append('<div class="concept">{{Concept}}</div>')
        
        # Image (if present)
        html_parts.append('{{#Image}}')
        html_parts.append('    <div class="visual">{{Image}}</div>')
        html_parts.append('{{/Image}}')
        
        # Sentence Cloze handling based on scaffold level
        # Note: Always include {{cloze:Sentence_Cloze}} to prevent "No Cloze Found" error
        # when note type is set to "Cloze"
        if self.scaffold_level == 'high':
            # High scaffolding: Show sentence cloze on front
            html_parts.append('{{#Sentence_Cloze}}')
            html_parts.append('    <div class="sentence">{{cloze:Sentence_Cloze}}</div>')
            html_parts.append('{{/Sentence_Cloze}}')
        else:
            # Low scaffolding: Hide sentence but still include cloze field
            # This satisfies Anki's requirement while keeping it invisible
            html_parts.append('{{#Sentence_Cloze}}')
            html_parts.append('    <div style="display: none;">{{cloze:Sentence_Cloze}}</div>')
            html_parts.append('{{/Sentence_Cloze}}')
        
        # Mode-specific input/audio
        if self.mode == 'verbal':
            # Verbal mode: Include typing field
            html_parts.append('<div class="type-prompt">Type Pinyin (no tones):</div>')
            html_parts.append('{{type:Pinyin_Clean}}')
        else:
            # Non-verbal mode: Large touch-friendly audio button
            # Note: Audio button uses IIFE to prevent zombie state bugs in Anki's WebView
            # Wrap Audio in hidden div to prevent Anki's native player from showing
            html_parts.append('<div class="audio-hidden">{{Audio}}</div>')
            html_parts.append('<button class="audio-button" onclick="(function() {')
            html_parts.append('    var hiddenContainer = document.querySelector(\'.audio-hidden\');')
            html_parts.append('    if (hiddenContainer) {')
            html_parts.append('        var audio = hiddenContainer.querySelector(\'audio\');')
            html_parts.append('        if (audio) { audio.play(); }')
            html_parts.append('    }')
            html_parts.append('})();">🔊</button>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)
    
    def _generate_back(self) -> str:
        """
        Generate Back Template HTML based on configuration.
        
        Returns:
            Back template HTML string
        """
        html_parts = ['<div class="card">']
        
        # Concept (always shown)
        html_parts.append('<div class="concept">{{Concept}}</div>')
        
        # Image (if present)
        html_parts.append('{{#Image}}')
        html_parts.append('    <div class="visual">{{Image}}</div>')
        html_parts.append('{{/Image}}')
        
        # Chinese and Pinyin
        html_parts.append('<div class="sentence">{{Chinese}}</div>')
        html_parts.append('<div style="font-size: 1.2em; color: #666;">{{Pinyin_Toned}}</div>')
        
        # Show sentence cloze on back if it exists
        html_parts.append('{{#Sentence_Cloze}}')
        html_parts.append('    <hr>')
        html_parts.append('    <div class="sentence">{{cloze:Sentence_Cloze}}</div>')
        html_parts.append('{{/Sentence_Cloze}}')
        
        # Audio (always on back)
        # Wrap Audio in hidden div to prevent Anki's native player from showing
        html_parts.append('<hr>')
        html_parts.append('<div class="audio-hidden">{{Audio}}</div>')
        
        # Show typed answer if in verbal mode
        if self.mode == 'verbal':
            html_parts.append('<div style="margin-top: 20px;">')
            html_parts.append('    <div class="type-prompt">Your answer:</div>')
            html_parts.append('    <div>{{type:Pinyin_Clean}}</div>')
            html_parts.append('</div>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)
    
    def generate_templates(self) -> Dict[str, str]:
        """
        Generate all template components (CSS, Front, Back).
        
        Returns:
            Dictionary with keys: 'css', 'front', 'back'
        """
        return {
            'css': self._generate_css(),
            'front': self._generate_front(),
            'back': self._generate_back()
        }


def push_configuration_to_anki(
    model_name: str,
    config: Dict[str, Any],
    anki_connect_url: str = "http://localhost:8765",
    template_name: Optional[str] = None
) -> bool:
    """
    Push template configuration to Anki via Anki-Connect API.
    
    This function:
    1. Generates templates using AnkiTemplateFactory
    2. Gets existing template names from the model (or uses provided name)
    3. Updates the model's templates via updateModelTemplates
    4. Updates the model's CSS via updateModelStyling
    
    Args:
        model_name: Name of the Anki note type (e.g., "Master Level 2")
        config: Configuration dictionary for template generation
        anki_connect_url: Anki-Connect server URL (default: http://localhost:8765)
        template_name: Optional template name to update. If None, will use the first
                      template found in the model, or "Card 1" as default.
    
    Returns:
        True if successful, False otherwise
    
    Raises:
        Exception: If Anki-Connect is not accessible or returns an error
    """
    # Generate templates
    factory = AnkiTemplateFactory(config)
    templates = factory.generate_templates()
    
    # Check if Anki is running and get template names
    ping_payload = {
        "action": "version",
        "version": 6
    }
    try:
        ping_response = requests.post(anki_connect_url, json=ping_payload, timeout=5)
        ping_response.raise_for_status()
        ping_result = ping_response.json()
        if ping_result.get("error"):
            raise Exception(f"Anki-Connect error: {ping_result['error']}")
    except requests.exceptions.ConnectionError:
        raise Exception("Cannot connect to Anki-Connect. Make sure Anki is running with AnkiConnect add-on installed.")
    except requests.exceptions.Timeout:
        raise Exception("Anki-Connect request timed out.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to communicate with Anki-Connect: {e}")
    
    # Get existing template names
    if template_name is None:
        model_templates_payload = {
            "action": "modelTemplates",
            "version": 6,
            "params": {
                "modelName": model_name
            }
        }
        try:
            templates_response = requests.post(
                anki_connect_url,
                json=model_templates_payload,
                timeout=10
            )
            templates_response.raise_for_status()
            templates_result = templates_response.json()
            if templates_result.get("error"):
                # If model doesn't exist or has no templates, use default
                template_name = "Card 1"
            else:
                existing_templates = templates_result.get("result", {})
                if existing_templates:
                    # Use the first template name found
                    template_name = list(existing_templates.keys())[0]
                else:
                    template_name = "Card 1"
        except Exception:
            # Fallback to default if we can't get template names
            template_name = "Card 1"
    
    # Prepare Anki-Connect payloads
    # Note: Anki-Connect expects templates in a specific format
    # For updateModelTemplates, we need to provide all card templates
    templates_payload = {
        template_name: {
            "Front": templates['front'],
            "Back": templates['back']
        }
    }
    
    # Update templates
    update_templates_payload = {
        "action": "updateModelTemplates",
        "version": 6,
        "params": {
            "model": {
                "name": model_name,
                "templates": templates_payload
            }
        }
    }
    
    # Update CSS
    update_styling_payload = {
        "action": "updateModelStyling",
        "version": 6,
        "params": {
            "model": {
                "name": model_name,
                "css": templates['css']
            }
        }
    }
    
    try:
        # Update templates
        templates_response = requests.post(
            anki_connect_url,
            json=update_templates_payload,
            timeout=10
        )
        templates_response.raise_for_status()
        templates_result = templates_response.json()
        if templates_result.get("error"):
            raise Exception(f"Failed to update templates: {templates_result['error']}")
        
        # Update CSS
        styling_response = requests.post(
            anki_connect_url,
            json=update_styling_payload,
            timeout=10
        )
        styling_response.raise_for_status()
        styling_result = styling_response.json()
        if styling_result.get("error"):
            raise Exception(f"Failed to update styling: {styling_result['error']}")
        
        return True
    
    except requests.exceptions.ConnectionError:
        raise Exception("Cannot connect to Anki-Connect. Make sure Anki is running with AnkiConnect add-on installed.")
    except requests.exceptions.Timeout:
        raise Exception("Anki-Connect request timed out.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to communicate with Anki-Connect: {e}")
    except Exception as e:
        raise Exception(f"Error pushing configuration to Anki: {e}")


# Example usage and testing
if __name__ == "__main__":
    # Example configurations
    verbal_config = {
        'mode': 'verbal',
        'dark_mode': False,
        'scaffold_level': 'high'
    }
    
    non_verbal_config = {
        'mode': 'non-verbal',
        'dark_mode': True,
        'scaffold_level': 'low'
    }
    
    # Generate templates for verbal child
    print("Generating templates for Verbal Child (High Scaffolding)...")
    factory = AnkiTemplateFactory(verbal_config)
    templates = factory.generate_templates()
    print("\n=== CSS ===")
    print(templates['css'][:200] + "...")
    print("\n=== Front Template ===")
    print(templates['front'])
    print("\n=== Back Template ===")
    print(templates['back'])
    
    # Uncomment to actually push to Anki:
    # Note: Model name might be "Master Level 2" or "CUMA - Master Level 2"
    # depending on how it was created in Anki
    # try:
    #     push_configuration_to_anki("Master Level 2", verbal_config)
    #     # Or: push_configuration_to_anki("CUMA - Master Level 2", verbal_config)
    #     print("\n✅ Successfully pushed configuration to Anki!")
    # except Exception as e:
    #     print(f"\n❌ Error: {e}")

