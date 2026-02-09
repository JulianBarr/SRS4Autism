import json
import os
import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from dotenv import load_dotenv, find_dotenv

# Force Env Load
load_dotenv(find_dotenv())

from database.kg_client import KnowledgeGraphClient
from database.services import ProfileService, CardService
from database.models import Profile
from ..core.config import PROMPT_TEMPLATES_FILE
from ..utils.common import load_json_file

logger = logging.getLogger(__name__)

class AgentService:
    @staticmethod
    def _is_chinese(text: str) -> bool:
        if not text: return False
        return bool(re.search(r'[\u4e00-\u9fff]', text))

    @staticmethod
    def _detect_cloze_syntax(text: str) -> bool:
        """Robustly detect cloze syntax ({{c1:: or [[c1::)."""
        if not text: return False
        return bool(re.search(r'\{\{c\d+::', text) or re.search(r'\[\[c\d+::', text))

    @staticmethod
    def _get_concept_nature(topic_id: str) -> str:
        """Query KG to determine if topic is Abstract, Concrete, or Grammar Rule."""
        if not topic_id: return "Unknown (Assume Concrete)"
        try:
            kg_client = KnowledgeGraphClient()
            escaped_topic_id = topic_id.replace('\\', '\\\\').replace('"', '\\"')
            
            # 1. Check if GrammarPoint (ASK query)
            sparql_grammar = f"""
            PREFIX srs-kg: <http://srs4autism.com/schema/>
            ASK {{
                {{ ?gp_uri srs-kg:sourceId "{escaped_topic_id}" }} UNION {{ BIND(IRI("{topic_id}") as ?gp_uri) }}
                ?gp_uri a srs-kg:GrammarPoint .
            }}
            """
            grammar_result = kg_client.query(sparql_grammar)
            if isinstance(grammar_result, dict) and grammar_result.get('boolean', False):
                return "Grammar Rule"

            # 2. Check Concreteness
            sparql_concreteness = f"""
            PREFIX srs-kg: <http://srs4autism.com/schema/>
            SELECT ?concreteness WHERE {{
                {{ ?w_uri srs-kg:sourceId "{escaped_topic_id}" }} UNION {{ BIND(IRI("{topic_id}") as ?w_uri) }}
                ?w_uri a srs-kg:Word ; srs-kg:concreteness ?concreteness .
            }} LIMIT 1
            """
            results = kg_client.query(sparql_concreteness)
            if results and 'results' in results and results['results']['bindings']:
                b = results['results']['bindings'][0]
                val_str = b.get('concreteness', {}).get('value')
                if val_str and float(val_str) < 3.0: return "Abstract Concept"
                if val_str: return "Concrete Object"
                
            if "grammar" in topic_id.lower(): return "Grammar Rule"
        except Exception as e:
            logger.error(f"KG Error: {e}")
        return "Unknown (Assume Concrete)"

    @staticmethod
    def _get_valid_api_key(passed_key: Optional[str]) -> Optional[str]:
        """
        Resolves API Key with SERVER PRIORITY.
        Always prefers the robust local .env key over potentially stale frontend headers.
        """
        # 1. PRIORITY: Server Environment Key (The "Source of Truth")
        load_dotenv(find_dotenv()) # Ensure latest env is loaded
        env_key = os.getenv("GEMINI_API_KEY")
        
        if env_key:
            # print("🔑 Using Server Environment Key (Priority)") # Uncomment for debug
            return env_key

        # 2. FALLBACK: Frontend Passed Key
        if passed_key:
            clean_key = passed_key.strip()
            # Basic sanity checks
            if (len(clean_key) > 20 and 
                "null" not in clean_key.lower() and 
                "undefined" not in clean_key.lower()):
                print("⚠️ Server Key missing. Falling back to Frontend Key.")
                return clean_key
            
        print("❌ No valid API Key found in Environment or Headers.")
        return None

    @staticmethod
    def _load_template_content(template_id: str) -> Optional[str]:
        """
        Loads template content with CASE-INSENSITIVE Matching.
        Fixes: 'english_vocab_cloze' (request) vs 'English_Vocab_Cloze' (file).
        """
        if not template_id:
            return None
        
        try:
            templates = load_json_file(PROMPT_TEMPLATES_FILE, [])
            target = template_id.lower().strip()
            
            print(f"🔍 Searching template: '{template_id}' (norm: '{target}')")
            
            for tmpl in templates:
                t_id = str(tmpl.get("id", "")).lower().strip()
                t_name = str(tmpl.get("name", "")).lower().strip()
                
                # Match against ID, Name, or Underscore/Hyphen variations
                if (target == t_id or 
                    target == t_name or 
                    target == t_name.replace(' ', '_') or
                    target == t_name.replace('-', '_')):
                    
                    print(f"✅ FOUND Template: '{tmpl.get('name')}'")
                    return tmpl.get("template_text") or tmpl.get("content")
            
            print(f"❌ Template '{template_id}' NOT FOUND.")
        except Exception as e:
            logger.error(f"Template Load Error: {e}")
        return None

    @staticmethod
    def _build_pedagogical_prompt(student_name: str, interests: str, roster_list: str, topic: str, concept_nature: str, quantity: int, user_instruction: str) -> str:
        prompt = f"""
SYSTEM: You are CUMA, an expert Special Education Content Generator assisting a PARENT.

CONTEXT:
- Student: {{student_name}}
- Interests: {{interests}}
- Character Roster: {{roster_list}}
- Concept: "{{topic}}"
- Concept Nature: {{concept_nature}}

YOUR CONSTITUTION (PEDAGOGICAL RULES):
1. **Character Usage:** You MUST use characters from the **Character Roster** ({{roster_list}}) in your examples. Do not use generic names if a roster is provided.
2. **Abstract Concepts:** If the concept is Abstract, generate a "Producer-Critic" style scenario.
3. **Interest Integration:** Weave interests ({{interests}}) into the examples.

TASK:
Generate {{quantity}} Anki cards for: "{{user_instruction}}".

OUTPUT FORMAT:
Return ONLY a JSON array of cards: 
[{{ "text_field": "...", "extra_field": "...", "tags": [...] }}]
"""
        return prompt.strip().format(
            student_name=student_name,
            interests=interests,
            roster_list=roster_list,
            topic=topic,
            concept_nature=concept_nature,
            quantity=quantity,
            user_instruction=user_instruction
        )

    @staticmethod
    def _build_universal_prompt(template_content: str, context: Dict[str, Any], user_instruction: str) -> str:
        """
        The Universal Adapter: Interpolates variables and appends technical specs.
        """
        # 1. Interpolation (Try to replace placeholders if they exist)
        prompt = template_content
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, str(value))

        # 2. Force-Inject Roster (The Fix)
        # We ensure the LLM sees the roster even if the template didn't ask for it.
        roster_str = context.get('character_roster', 'Generic characters')

        # 3. Technical Constitution (Safety Layer)
        technical_specs = f"""
------------------------------------------------------------------
SYSTEM OVERRIDE: TECHNICAL & CONTENT SPECIFICATIONS
You must adhere to these rules above all else:

1. **OUTPUT FORMAT:** Return ONLY a raw JSON array.
   - Example: `[{{"text_field": "...", "extra_field": "...", "tags": [...]}}]`
   
2. **CLOZE SYNTAX:** - You MUST use Anki syntax: `[[c1::target_word]]`. 
   - DO NOT use underscores (`_____`) or parentheses `(word)`.

3. **MANDATORY CONTENT:**
   - **Instruction:** "{user_instruction}"
   - **Quantity:** {context.get('quantity', 3)}
   - **CHARACTER ROSTER:** {roster_str}
     (CRITICAL: You MUST use characters from this list in your sentences! Do not use generic names like 'Tom' or 'Alice' unless they are in the list.)
------------------------------------------------------------------
"""
        return prompt + "\n" + technical_specs

    @staticmethod
    def _call_llm(system_prompt: str, passed_key: Optional[str] = None) -> str:
        # 1. Validate/Sanitize Key
        api_key = AgentService._get_valid_api_key(passed_key)
        
        if not api_key:
            print("⚠️ No valid API Key. Returning Mock.")
            return AgentService._get_mock_response()

        try:
            if os.getenv("GEMINI_API_KEY") or (api_key and not api_key.startswith("sk-")):
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("models/gemini-2.0-flash") # Use Flash for speed
                response = model.generate_content(system_prompt)
                return response.text
            else:
                from openai import OpenAI
                base_url = os.getenv("DEEPSEEK_API_BASE") or os.getenv("OPENAI_BASE_URL")
                client = OpenAI(api_key=api_key, base_url=base_url)
                response = client.chat.completions.create(
                    model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
                    messages=[{"role": "user", "content": system_prompt}]
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return "[]"

    @staticmethod
    def _get_mock_response() -> str:
        return json.dumps([{"text_field": "Mock Card [[c1::Answer]]", "tags": ["Mock"]}])

    @staticmethod
    def _resolve_profile_id(db: Session, identifier: str) -> Optional[str]:
        if not identifier: return None
        # Try ID, then Name, then Fuzzy
        p = ProfileService.get_by_id(db, identifier) or \
            db.query(Profile).filter(Profile.name == identifier).first() or \
            db.query(Profile).filter(Profile.name.ilike(f"%{identifier.split('(')[0].strip()}%")).first()
        return p.id if p is not None else None

    @staticmethod
    def generate_cards(topic_id: str, roster_id: str, template_id: str, user_instruction: str, quantity: int, db: Session, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        print(f"🚀 Generating: '{topic_id}' | Template: '{template_id}' | Qty: {quantity}")

        # 1. Resolve Data
        real_profile_id = AgentService._resolve_profile_id(db, roster_id) or roster_id
        profile = ProfileService.get_by_id(db, real_profile_id)
        
        student_name = "Student"
        interests = "General"
        roster_str = "Generic Characters"
        
        if profile:
            p_dict = ProfileService.profile_to_dict(db, profile)
            student_name = p_dict.get('name', 'Student')
            interests = ", ".join(p_dict.get('interests', [])) or "General"
            roster = p_dict.get('character_roster', [])
            if roster: roster_str = ", ".join(roster)

        # TEMPLATE FIRST STRATEGY
        template_content = AgentService._load_template_content(template_id)
        
        if template_content:
            print(f"👉 Strategy: TEMPLATE MODE")
            context = {
                "student_name": student_name,
                "interests": interests,
                "character_roster": roster_str,
                "roster": roster_str,
                "topic": topic_id,
                "quantity": quantity
            }
            system_prompt = AgentService._build_universal_prompt(template_content, context, user_instruction)
        else:
            print("👉 Strategy: AGENT MODE (Constitution)")
            concept_nature = AgentService._get_concept_nature(topic_id)
            print(f"🧠 Concept Nature: {concept_nature}")
            
            # Use pedagogical prompt with character roster
            system_prompt = AgentService._build_pedagogical_prompt(
                student_name=student_name,
                interests=interests,
                roster_list=roster_str,
                topic=topic_id,
                concept_nature=concept_nature,
                quantity=quantity,
                user_instruction=user_instruction
            )

        # 3. Execution
        response_text = AgentService._call_llm(system_prompt, api_key)

        # 4. Parse & Save
        saved_cards = []
        try:
            clean_text = re.sub(r'```json\s*|\s*```', '', response_text, flags=re.IGNORECASE).strip()
            start = clean_text.find('[')
            end = clean_text.rfind(']') + 1
            if start != -1 and end != -1: clean_text = clean_text[start:end]
            cards_data = json.loads(clean_text)
        except Exception as e:
            logger.error(f"JSON Parse Error: {e}")
            return []

        for card in cards_data[:quantity]:
            if isinstance(card, str): card = {"text_field": card}
            
            text_field = card.get("text_field", card.get("front", ""))
            extra_field = card.get("extra_field", card.get("back", ""))
            tags = card.get("tags", ["AI_Generated"])
            
            # AUTO-REPAIR: Underscores -> Cloze
            if "___" in text_field and topic_id and "[[" not in text_field:
                text_field = re.sub(r'_+', f"[[c1::{topic_id}]]", text_field)
                print("🔧 Auto-repaired cloze syntax")

            # Determine Type
            has_cloze = AgentService._detect_cloze_syntax(text_field)
            if has_cloze:
                card_type = "interactive_cloze"
                note_type = "CUMA - Interactive Cloze"
            else:
                card_type = "basic"
                note_type = "CUMA - Basic"

            staging = {
                "card_type": card_type,
                "note_type": note_type,
                "tags": tags,
                "text_field": text_field,
                "extra_field": extra_field
            }

            try:
                db_card = CardService.create(db, real_profile_id, card_type, staging, "pending")
                staging["id"] = str(db_card.id)
                saved_cards.append(staging)
                print(f"💾 Saved #{db_card.id} ({card_type})")
            except Exception as e:
                logger.error(f"Save Failed: {e}")

        return saved_cards
