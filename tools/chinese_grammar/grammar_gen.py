#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chinese Grammar Sentence Generator (Version 2.0 - Pragmatic-Based).

This script queries the Knowledge Graph for GrammarPoint instances and
generates example sentences using pragmatic imitation instead of structure-based
templates.

Version: 2.0 (Pragmatic-Based Migration)
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Add project root to path for imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import google.generativeai as genai
except ImportError:
    print("ERROR: google-generativeai is not installed.")
    print("Please install it with: pip install google-generativeai")
    sys.exit(1)

try:
    from backend.database.kg_client import KnowledgeGraphClient
except ImportError:
    print("ERROR: Could not import KnowledgeGraphClient.")
    print("Please ensure the backend module is accessible.")
    sys.exit(1)

# Load environment variables
load_dotenv()

# --- Configuration ---
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("Error: GOOGLE_API_KEY environment variable not set.")
    print("Please create a .env file with GOOGLE_API_KEY='your_key_here'")
    sys.exit(1)

MODEL_NAME = "gemini-2.5-pro"
OUTPUT_FILENAME = "chinese_grammar_sentences.json"

# SPARQL Query to fetch GrammarPoint instances
# Filters for isChildFriendly = true (if property exists)
SPARQL_QUERY = """
PREFIX srs-kg: <http://srs4autism.com/schema/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX : <http://srs4autism.com/instance/>

SELECT ?uri ?label ?explanation ?anchorExample 
       (GROUP_CONCAT(DISTINCT ?keyword; separator=", ") AS ?keywords)
       (GROUP_CONCAT(DISTINCT ?pragCtx; separator=" | ") AS ?pragmaticContext)
WHERE {
    ?uri a srs-kg:GrammarPoint .
    ?uri rdfs:label ?label .
    
    # Filter: Include if isChildFriendly is true OR property doesn't exist
    # (This allows grammar points without the property to be included)
    OPTIONAL {
        ?uri srs-kg:isChildFriendly ?isChildFriendly .
    }
    FILTER (!BOUND(?isChildFriendly) || ?isChildFriendly = true)
    
    # Get explanation
    OPTIONAL {
        ?uri srs-kg:explanation ?explanation .
    }
    
    # Get anchor example (for imitation)
    OPTIONAL {
        ?uri srs-kg:anchorExample ?anchorExample .
    }
    
    # Get keywords (multiple possible)
    OPTIONAL {
        ?uri srs-kg:keyword ?keyword .
    }
    
    # Get pragmatic context (multiple possible)
    OPTIONAL {
        ?uri srs-kg:pragmaticContext ?pragCtx .
    }
}
GROUP BY ?uri ?label ?explanation ?anchorExample
"""


def configure_api():
    """Configures the Google Generative AI client."""
    try:
        genai.configure(api_key=API_KEY)
        print("✅ Google API configured successfully.")
    except Exception as e:
        print(f"❌ Error configuring Google API: {e}")
        sys.exit(1)


def query_grammar_points() -> List[Dict[str, Any]]:
    """
    Query the Knowledge Graph for GrammarPoint instances.
    
    Returns:
        List of dictionaries containing grammar point data
    """
    print("Querying Knowledge Graph for GrammarPoint instances...")
    
    try:
        kg_client = KnowledgeGraphClient()
        results = kg_client.query(SPARQL_QUERY)
        
        bindings = results.get("results", {}).get("bindings", [])
        print(f"  Found {len(bindings)} grammar points")
        
        grammar_points = []
        for binding in bindings:
            gp = {
                "uri": binding.get("uri", {}).get("value", ""),
                "label": _extract_literal_value(binding.get("label", {})),
                "explanation": _extract_literal_value(binding.get("explanation", {})),
                "anchorExample": _extract_literal_value(binding.get("anchorExample", {})),
                "keywords": _extract_keywords_from_binding(binding),
                "pragmaticContext": _extract_pragmatic_context_from_binding(binding),
            }
            grammar_points.append(gp)
        
        return grammar_points
        
    except Exception as e:
        print(f"❌ Error querying Knowledge Graph: {e}")
        import traceback
        traceback.print_exc()
        return []


def _extract_literal_value(binding_item: Dict) -> str:
    """Extract string value from SPARQL binding."""
    if not binding_item:
        return ""
    return binding_item.get("value", "")


def _extract_keywords_from_binding(binding: Dict) -> List[str]:
    """Extract keywords from binding (handles GROUP_CONCAT with comma separator)."""
    keywords_str = _extract_literal_value(binding.get("keywords", {}))
    if not keywords_str:
        return []
    # GROUP_CONCAT uses ", " as separator
    return [k.strip() for k in keywords_str.split(",") if k.strip()]


def _extract_pragmatic_context_from_binding(binding: Dict) -> List[str]:
    """Extract pragmatic context from binding (handles GROUP_CONCAT with | separator)."""
    context_str = _extract_literal_value(binding.get("pragmaticContext", {}))
    if not context_str:
        return []
    # GROUP_CONCAT uses " | " as separator
    return [c.strip() for c in context_str.split("|") if c.strip()]


def generate_sentences_pragmatic(
    label: str,
    explanation: str = "",
    anchor_example: str = "",
    keywords: List[str] = None,
    pragmatic_context: List[str] = None
) -> List[str]:
    """
    Generate sentences using pragmatic imitation approach.
    
    Args:
        label: Grammar point label (Chinese)
        explanation: Explanation of the grammar point
        anchor_example: Example sentence to imitate
        keywords: List of keywords to use
        pragmatic_context: List of usage contexts
        
    Returns:
        List of generated sentences
    """
    model = genai.GenerativeModel(MODEL_NAME)
    
    # Build context strings
    keywords_str = ", ".join(keywords) if keywords else "None specified"
    context_str = "\n".join([f"- {ctx}" for ctx in pragmatic_context]) if pragmatic_context else "None specified"
    
    # Build prompt
    prompt = f"""Role: Chinese Language Teacher for a child.
Task: Create 5 sentences using the grammar point: "{label}".

Reference Info:
- Concept: {explanation if explanation else "Not provided"}
- Anchor Example (Imitate this pattern): "{anchor_example if anchor_example else "Not provided"}"
- Usage Context: {context_str}
- Keywords to use: {keywords_str}

Requirements:
1. Imitate the structure of the Anchor Example but change the subject/object/verb to fit the Context.
2. Sentences must be simple, concrete, and suitable for a 6-12 year old child.
3. Output format: A JSON list of strings ["sentence 1", "sentence 2", ...].
"""
    
    json_schema = {
        "type": "ARRAY",
        "items": {
            "type": "STRING"
        }
    }
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=json_schema
            )
        )
        
        sentences = json.loads(response.text)
        if not isinstance(sentences, list):
            return []
        return [s for s in sentences if s and isinstance(s, str)]
        
    except Exception as e:
        print(f"    ⚠️  Error generating sentences: {e}")
        if hasattr(response, 'text') and response.text:
            print(f"    Response text: {response.text[:200]}")
        return []


def main():
    """Main function to generate sentences from grammar points."""
    print("=" * 80)
    print("Chinese Grammar Sentence Generator")
    print("Version 2.0 (Pragmatic-Based Migration)")
    print("=" * 80)
    print()
    
    # Configure API
    configure_api()
    
    # Query grammar points from KG
    grammar_points = query_grammar_points()
    
    if not grammar_points:
        print("❌ No grammar points found. Exiting.")
        return
    
    print(f"\nGenerating sentences for {len(grammar_points)} grammar points...")
    print()
    
    results = []
    
    for i, gp in enumerate(grammar_points):
        label = gp.get("label", "Unknown")
        print(f"[{i+1}/{len(grammar_points)}] Processing: {label}")
        
        sentences = generate_sentences_pragmatic(
            label=label,
            explanation=gp.get("explanation", ""),
            anchor_example=gp.get("anchorExample", ""),
            keywords=gp.get("keywords", []),
            pragmatic_context=gp.get("pragmaticContext", [])
        )
        
        if sentences:
            print(f"  ✅ Generated {len(sentences)} sentences")
            results.append({
                "grammar_point": label,
                "uri": gp.get("uri", ""),
                "generated_sentences": sentences
            })
        else:
            print(f"  ⚠️  No sentences generated")
        
        # Rate limiting
        time.sleep(1)
    
    # Save results
    try:
        output_path = SCRIPT_DIR / OUTPUT_FILENAME
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Success! Generated sentences saved to '{output_path}'")
        print(f"   Total grammar points processed: {len(results)}")
    except Exception as e:
        print(f"\n❌ Error saving results: {e}")


if __name__ == "__main__":
    main()
