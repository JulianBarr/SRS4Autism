"""
Agent Service for Card Generation (FIXED: ID Resolution + Status)
"""
import json
import os
import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database.kg_client import KnowledgeGraphClient
from database.services import ProfileService, CardService
from database.models import Profile
from ..core.config import PROMPT_TEMPLATES_FILE
from ..utils.common import load_json_file

logger = logging.getLogger(__name__)

# --- PROMPTS ---

# 1. English Grammar Prompt
ENGLISH_GRAMMAR_PROMPT = """SYSTEM: You are a Special Ed English Teacher for {student_name}.
TASK: Create {quantity} Anki cards for English Grammar Point: "{grammar_label}".
CONTEXT: {grammar_explanation}
NOTE TYPE: {template_note_type}
INTERESTS: {interests}

OUTPUT FORMAT:
Return a JSON array. 
For "CUMA - Interactive Cloze":
- text_field: English Sentence with [[c1::target_grammar]] cloze.
- extra_field: Chinese Translation + Grammar Note.
- tags: ["Grammar", "{grammar_label}"]

STRICT: Target grammar MUST be the cloze."""

# 2. Chinese Grammar Prompt
CHINESE_GRAMMAR_PROMPT = """SYSTEM: You are a Special Ed Chinese Teacher for {student_name}.
TASK: Create {quantity} Anki cards for CHINESE Grammar Point: "{grammar_label}".
CONTEXT: {grammar_explanation}
NOTE TYPE: {template_note_type}
INTERESTS: {interests}

OUTPUT FORMAT:
Return a JSON array.
For "CUMA - Interactive Cloze":
- text_field: Chinese Sentence with [[c1::target_grammar]] cloze. (Simplified Chinese)
- extra_field: English Translation + Grammar Note.
- tags: ["Chinese Grammar", "{grammar_label}"]

STRICT: The Chinese grammar structure MUST be the cloze. Do NOT cloze the English."""

class AgentService:
    @staticmethod
    def _is_chinese(text: str) -> bool:
        """Check if text contains Chinese characters."""
        if not text: return False
        return bool(re.search(r'[\u4e00-\u9fff]', text))

    @staticmethod
    def _determine_topic_type(topic_id: str) -> str:
        if not topic_id: return "vocabulary"
        normalized = topic_id.lower()
        if "grammar" in normalized:
            return "grammar"
        return "vocabulary"

    @staticmethod
    def _fetch_grammar_point(topic_id: str) -> Dict[str, Any]:
        try:
            kg_client = KnowledgeGraphClient()
            # Escape SPARQL string literals: escape backslashes and quotes
            escaped_topic_id = topic_id.replace('\\', '\\\\').replace('"', '\\"')
            
            # Only try URI binding if topic_id looks like a URI (starts with http:// or https://)
            # Otherwise, just use the sourceId lookup
            if topic_id.startswith('http://') or topic_id.startswith('https://'):
                # Use IRI() function to properly construct URI
                sparql = f"""
                PREFIX srs-kg: <http://srs4autism.com/schema/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?label_zh ?label_en ?explanation_zh ?explanation_en
                WHERE {{
                    {{ ?gp_uri srs-kg:sourceId "{escaped_topic_id}" }} UNION {{ BIND(IRI("{topic_id}") as ?gp_uri) }}
                    ?gp_uri a srs-kg:GrammarPoint .
                    OPTIONAL {{ ?gp_uri rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }}
                    OPTIONAL {{ ?gp_uri rdfs:label ?label_en . FILTER(LANG(?label_en) = "en") }}
                    OPTIONAL {{ ?gp_uri srs-kg:explanation ?explanation_zh . FILTER(LANG(?explanation_zh) = "zh") }}
                    OPTIONAL {{ ?gp_uri srs-kg:explanation ?explanation_en . FILTER(LANG(?explanation_en) = "en") }}
                }} LIMIT 1
                """
            else:
                # For non-URI topic_ids, only use sourceId lookup
                sparql = f"""
                PREFIX srs-kg: <http://srs4autism.com/schema/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?label_zh ?label_en ?explanation_zh ?explanation_en
                WHERE {{
                    ?gp_uri srs-kg:sourceId "{escaped_topic_id}" .
                    ?gp_uri a srs-kg:GrammarPoint .
                    OPTIONAL {{ ?gp_uri rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }}
                    OPTIONAL {{ ?gp_uri rdfs:label ?label_en . FILTER(LANG(?label_en) = "en") }}
                    OPTIONAL {{ ?gp_uri srs-kg:explanation ?explanation_zh . FILTER(LANG(?explanation_zh) = "zh") }}
                    OPTIONAL {{ ?gp_uri srs-kg:explanation ?explanation_en . FILTER(LANG(?explanation_en) = "en") }}
                }} LIMIT 1
                """
            results = kg_client.query(sparql)
            if results and 'results' in results and results['results']['bindings']:
                b = results['results']['bindings'][0]
                return {
                    'label': b.get('label_zh', {}).get('value') or b.get('label_en', {}).get('value', topic_id),
                    'explanation': b.get('explanation_zh', {}).get('value') or b.get('explanation_en', {}).get('value', '')
                }
        except Exception as e:
            logger.error(f"KG Error: Query execution failed: {e}")
            # Return default values so card generation can continue
        return {'label': topic_id, 'explanation': ''}

    @staticmethod
    def _query_knowledge_graph(user_instruction: str) -> str:
        """
        Query knowledge graph for grammar context based on user instruction.
        Returns grammar explanation string for injection into prompts.
        """
        if not user_instruction:
            return ""
        
        try:
            kg_client = KnowledgeGraphClient()
            # Escape SPARQL string literals
            escaped_instruction = user_instruction.replace('\\', '\\\\').replace('"', '\\"')
            
            # Search for grammar points that match keywords in the instruction
            # This is a simple keyword-based search - can be enhanced later
            sparql = f"""
            PREFIX srs-kg: <http://srs4autism.com/schema/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?label_zh ?label_en ?explanation_zh ?explanation_en
            WHERE {{
                ?gp_uri a srs-kg:GrammarPoint .
                OPTIONAL {{ ?gp_uri rdfs:label ?label_zh . FILTER(LANG(?label_zh) = "zh") }}
                OPTIONAL {{ ?gp_uri rdfs:label ?label_en . FILTER(LANG(?label_en) = "en") }}
                OPTIONAL {{ ?gp_uri srs-kg:explanation ?explanation_zh . FILTER(LANG(?explanation_zh) = "zh") }}
                OPTIONAL {{ ?gp_uri srs-kg:explanation ?explanation_en . FILTER(LANG(?explanation_en) = "en") }}
                FILTER (
                    CONTAINS(LCASE(?label_en), LCASE("{escaped_instruction}")) ||
                    CONTAINS(LCASE(?label_zh), LCASE("{escaped_instruction}")) ||
                    CONTAINS(LCASE(?explanation_en), LCASE("{escaped_instruction}")) ||
                    CONTAINS(LCASE(?explanation_zh), LCASE("{escaped_instruction}"))
                )
            }} LIMIT 3
            """
            results = kg_client.query(sparql)
            if results and 'results' in results and results['results']['bindings']:
                explanations = []
                for binding in results['results']['bindings']:
                    expl = binding.get('explanation_en', {}).get('value') or binding.get('explanation_zh', {}).get('value')
                    if expl:
                        explanations.append(expl)
                if explanations:
                    return " | ".join(explanations[:2])  # Return up to 2 explanations
        except Exception as e:
            logger.error(f"KG Query Error for instruction '{user_instruction}': {e}")
        return ""

    @staticmethod
    def _detect_cloze_syntax(text: str) -> bool:
        """
        Detect if text contains cloze deletion syntax.
        Returns True if {{c1:: or [[c1:: patterns are found.
        """
        if not text:
            return False
        # Check for both {{c1:: and [[c1:: patterns
        return bool(re.search(r'\{\{c\d+::', text) or re.search(r'\[\[c\d+::', text))

    @staticmethod
    def _load_template(template_id: str) -> Optional[Dict[str, Any]]:
        try:
            templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
            for tmpl in templates:
                if tmpl.get("id") == template_id or tmpl.get("name") == template_id:
                    return tmpl
        except Exception:
            pass
        return None

    @staticmethod
    def _call_llm(system_prompt: str, api_key: Optional[str] = None) -> str:
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        
        if not api_key:
            print("⚠️ No API Key found. Returning Mock Data.")
            return AgentService._get_mock_response()

        try:
            if os.getenv("GEMINI_API_KEY") or (api_key and not api_key.startswith("sk-")):
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("models/gemini-2.5-flash")
                response = model.generate_content(system_prompt)
                return response.text
            else:
                from openai import OpenAI
                base_url = os.getenv("DEEPSEEK_API_BASE") or os.getenv("OPENAI_BASE_URL")
                
                model_name = os.getenv("LLM_MODEL")
                if not model_name:
                    model_name = "gpt-3.5-turbo"

                print(f"📡 Calling LLM: {base_url} | Model: {model_name}")

                client = OpenAI(api_key=api_key, base_url=base_url)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": system_prompt}]
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"❌ LLM Call Failed: {e}")
            return "[]"

    @staticmethod
    def _get_mock_response() -> str:
        return json.dumps([{"text_field": "Mock Card [[c1::Answer]]", "tags": ["Mock"]}])

    # --- HELPER: Resolve ID or Name (NEW) ---
    @staticmethod
    def _resolve_profile_id(db: Session, identifier: str) -> Optional[str]:
        """Resolves a UUID or Name string to a valid Profile ID."""
        # 1. Try direct ID lookup
        profile = ProfileService.get_by_id(db, identifier)
        if profile:
            return profile.id
            
        # 2. Try lookup by Name (exact match)
        profile = db.query(Profile).filter(Profile.name == identifier).first()
        if profile:
            return profile.id
            
        # 3. Try fuzzy lookup
        simple_name = identifier.split('(')[0].strip()
        profile = db.query(Profile).filter(Profile.name.ilike(f"%{simple_name}%")).first()
        if profile:
            return profile.id
            
        return None

    @staticmethod
    def generate_cards(topic_id: str, roster_id: str, template_id: str, user_instruction: str, quantity: int, db: Session, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        print(f"🚀 Generating cards for: {topic_id}")
        
        # FIX 1: Respect @quantity and @roster Inputs
        # Resolve Real ID
        real_profile_id = AgentService._resolve_profile_id(db, roster_id)
        if not real_profile_id:
            print(f"⚠️ Could not resolve Profile ID for: {roster_id}. Using as-is.")
            real_profile_id = roster_id 
        else:
            print(f"✅ Resolved '{roster_id}' -> Profile ID: {real_profile_id}")

        # Fetch Profile from DB using roster_id (FIX 1)
        profile = ProfileService.get_by_id(db, real_profile_id)
        if not profile:
            print(f"⚠️ Profile not found for ID: {real_profile_id}. Cards will be saved but may not appear in curation.")
        
        # Extract profile.name and profile.interests (FIX 1)
        student_name = "Student"
        interests = "General"
        if profile:
            p_dict = ProfileService.profile_to_dict(db, profile)
            student_name = p_dict.get('name', 'Student')
            interests_list = p_dict.get('interests', [])
            interests = ", ".join(interests_list) if interests_list else "General"
            print(f"📋 Student: {student_name}, Interests: {interests}, Quantity: {quantity}")

        # Fetch Context
        grammar_point = AgentService._fetch_grammar_point(topic_id)
        topic_type = AgentService._determine_topic_type(topic_id)
        template = AgentService._load_template(template_id)
        template_note_type = template.get('note_type', 'CUMA - Basic') if template else "CUMA - Basic"
        grammar_label = grammar_point.get('label', topic_id)

        # FIX 3: Inject Knowledge Graph Details
        grammar_explanation = grammar_point.get('explanation', '')
        # If topic_id is "Grammar" or instruction implies grammar, query KG
        if topic_type == "grammar" or "grammar" in user_instruction.lower():
            kg_context = AgentService._query_knowledge_graph(user_instruction)
            if kg_context:
                grammar_explanation = f"{grammar_explanation}\n\nAdditional Context: {kg_context}".strip()
                print(f"📚 Injected KG context: {kg_context[:50]}...")

        # 3. PROMPT SELECTION
        if topic_type == "grammar":
            is_chinese_topic = AgentService._is_chinese(topic_id) or AgentService._is_chinese(grammar_label)
            if is_chinese_topic:
                print("👉 Mode: CHINESE GRAMMAR")
                system_prompt = CHINESE_GRAMMAR_PROMPT.format(
                    student_name=student_name,
                    quantity=quantity,  # FIX 1: Pass quantity to prompt
                    grammar_label=grammar_label,
                    grammar_explanation=grammar_explanation,  # FIX 3: Use enhanced explanation
                    template_note_type=template_note_type,
                    interests=interests  # FIX 1: Inject interests
                )
            else:
                print("👉 Mode: ENGLISH GRAMMAR")
                system_prompt = ENGLISH_GRAMMAR_PROMPT.format(
                    student_name=student_name,
                    quantity=quantity,  # FIX 1: Pass quantity to prompt
                    grammar_label=grammar_label,
                    grammar_explanation=grammar_explanation,  # FIX 3: Use enhanced explanation
                    template_note_type=template_note_type,
                    interests=interests  # FIX 1: Inject interests
                )
            system_prompt += f"\nUSER INSTRUCTION: {user_instruction}"
        else:
            print("👉 Mode: VOCABULARY TEMPLATE")
            base_prompt = template.get('content', '') if template else ''
            # FIX 1: Include quantity and interests in vocabulary prompt too
            system_prompt = f"SYSTEM: You are a Special Ed Teacher for {student_name}.\nTASK: Create exactly {quantity} Anki cards.\nINTERESTS: {interests}\n{base_prompt}\nUSER INSTRUCTION: {user_instruction}\nNOTE TYPE: {template_note_type}\n\nReturn a JSON array with {quantity} cards."

        # 4. Execute
        response_text = AgentService._call_llm(system_prompt, api_key)
        
        # 5. Parse & Save
        try:
            clean_text = re.sub(r'```json\s*|\s*```', '', response_text, flags=re.IGNORECASE).strip()
            start = clean_text.find('[')
            end = clean_text.rfind(']') + 1
            if start != -1 and end != -1: clean_text = clean_text[start:end]
            cards = json.loads(clean_text)
        except Exception:
            print("❌ Error parsing JSON response")
            return []

        saved_cards = []
        # FIX 1: Limit to quantity (already done with [:quantity], but ensure we respect it)
        for card in cards[:quantity]:
            # FIX 4: Robust Output Parsing - Handle case where LLM returns strings instead of JSON objects
            if isinstance(card, str):
                card = {"text_field": card, "tags": [], "extra_field": ""}
            
            # Extract text_field for cloze detection
            text_field = card.get("text_field", card.get("front", "")) if isinstance(card, dict) else str(card)
            
            # FIX 2: Fix "Basic vs Cloze" Conflict
            # Check if text contains cloze syntax
            has_cloze = AgentService._detect_cloze_syntax(text_field)
            
            # Determine card_type and note_type based on cloze detection
            if has_cloze:
                card_type = "interactive_cloze"  # FIX: Use "interactive_cloze" not "cloze"
                note_type = "CUMA - Interactive Cloze"
                print(f"🔍 Detected cloze syntax, forcing: {note_type} (card_type: {card_type})")
            else:
                # Default based on template, but can be overridden
                card_type = "interactive_cloze" if "interactive" in template_note_type.lower() else "basic"
                note_type = template_note_type
            
            staging_content = {
                "card_type": card_type,  # FIX 2: Use detected card_type
                "note_type": note_type,  # FIX 2: Use detected note_type
                "tags": card.get("tags", ["AI_Generated"]) if isinstance(card, dict) else [],
                "text_field": text_field,
                "extra_field": card.get("extra_field", card.get("back", "")) if isinstance(card, dict) else ""
            }
            
            # Use REAL ID + STATUS="pending"
            try:
                db_card = CardService.create(
                    db=db, 
                    profile_id=real_profile_id,
                    card_type=staging_content['card_type'], 
                    content=staging_content,
                    status="pending"
                )
                # Add database ID to the card
                staging_content["id"] = str(db_card.id)
                staging_content["status"] = "pending"
                saved_cards.append(staging_content)
                print(f"💾 Saved card #{db_card.id} to profile '{real_profile_id}' (status: {db_card.status}, card_type: {db_card.card_type}): {staging_content['text_field'][:30]}...")
            except Exception as e:
                logger.error(f"❌ Failed to save card: {e}")
                print(f"Card content: {staging_content}")
                raise

        return saved_cards
