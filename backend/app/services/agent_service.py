"""
Agent Service for Card Generation (FIXED: User Config Only)
"""
import json
import os
import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database.kg_client import KnowledgeGraphClient
from database.services import ProfileService, CardService
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
        """Determine if topic is Grammar or Vocabulary."""
        if not topic_id: return "vocabulary"
        normalized = topic_id.lower()
        if "grammar" in normalized:
            return "grammar"
        return "vocabulary"

    @staticmethod
    def _fetch_grammar_point(topic_id: str) -> Dict[str, Any]:
        """Fetch Grammar Point details."""
        try:
            kg_client = KnowledgeGraphClient()
            sparql = f"""
            PREFIX srs-kg: <http://srs4autism.com/schema/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?label_zh ?label_en ?explanation_zh ?explanation_en
            WHERE {{
                {{ ?gp_uri srs-kg:sourceId "{topic_id}" }} UNION {{ BIND(<{topic_id}> as ?gp_uri) }}
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
            logger.error(f"KG Error: {e}")
        return {'label': topic_id, 'explanation': ''}

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
            # GEMINI
            if os.getenv("GEMINI_API_KEY") or (api_key and not api_key.startswith("sk-")):
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("models/gemini-2.5-flash")
                response = model.generate_content(system_prompt)
                return response.text
            # OPENAI COMPATIBLE (DeepSeek, etc.)
            else:
                from openai import OpenAI
                base_url = os.getenv("DEEPSEEK_API_BASE") or os.getenv("OPENAI_BASE_URL")
                
                # STRICT USER CONFIGURATION:
                # We trust the env var. If missing, we default to standard gpt-3.5-turbo
                # but log a warning so the user knows to fix their .env
                model_name = os.getenv("LLM_MODEL")
                if not model_name:
                    logger.warning("LLM_MODEL not set in environment. Defaulting to 'gpt-3.5-turbo'.")
                    print("⚠️ LLM_MODEL not set. Using 'gpt-3.5-turbo'. Check your .env!")
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

    @staticmethod
    def generate_cards(topic_id: str, roster_id: str, template_id: str, user_instruction: str, quantity: int, db: Session, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        print(f"🚀 Generating cards for: {topic_id}")
        
        # 1. Fetch Context
        grammar_point = AgentService._fetch_grammar_point(topic_id)
        profile = ProfileService.get_by_id(db, roster_id)
        
        student_name = "Student"
        interests = "General"
        if profile:
            p_dict = ProfileService.profile_to_dict(db, profile)
            student_name = p_dict.get('name', 'Student')
            interests = ", ".join(p_dict.get('interests', []))

        topic_type = AgentService._determine_topic_type(topic_id)
        template = AgentService._load_template(template_id)
        template_note_type = template.get('note_type', 'CUMA - Basic') if template else "CUMA - Basic"
        grammar_label = grammar_point.get('label', topic_id)

        # 2. PROMPT SELECTION LOGIC
        if topic_type == "grammar":
            # Detect Language (Chinese vs English)
            is_chinese_topic = AgentService._is_chinese(topic_id) or AgentService._is_chinese(grammar_label)
            
            if is_chinese_topic:
                print("👉 Mode: CHINESE GRAMMAR")
                system_prompt = CHINESE_GRAMMAR_PROMPT.format(
                    student_name=student_name,
                    quantity=quantity,
                    grammar_label=grammar_label,
                    grammar_explanation=grammar_point.get('explanation', ''),
                    template_note_type=template_note_type,
                    interests=interests
                )
            else:
                print("👉 Mode: ENGLISH GRAMMAR")
                system_prompt = ENGLISH_GRAMMAR_PROMPT.format(
                    student_name=student_name,
                    quantity=quantity,
                    grammar_label=grammar_label,
                    grammar_explanation=grammar_point.get('explanation', ''),
                    template_note_type=template_note_type,
                    interests=interests
                )
            
            # Add user instructions
            system_prompt += f"\nUSER INSTRUCTION: {user_instruction}"

        else:
            # VOCABULARY
            print("👉 Mode: VOCABULARY TEMPLATE")
            base_prompt = template.get('content', '') if template else ''
            system_prompt = f"Teacher for {student_name}. Interests: {interests}. Task: {base_prompt}. Instruction: {user_instruction}. Return JSON for {template_note_type}."

        # 3. Execute
        response_text = AgentService._call_llm(system_prompt, api_key)
        
        # 4. Parse & Save
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
        for card in cards[:quantity]:
            staging_content = {
                "card_type": "interactive_cloze" if "interactive" in template_note_type.lower() else "basic",
                "note_type": template_note_type,
                "tags": card.get("tags", ["AI_Generated"]),
                "text_field": card.get("text_field", card.get("front", "")),
                "extra_field": card.get("extra_field", card.get("back", ""))
            }
            CardService.create(db=db, profile_id=roster_id, card_type=staging_content['card_type'], content=staging_content)
            saved_cards.append(staging_content)
            print(f"💾 Saved: {staging_content['text_field'][:20]}...")

        return saved_cards
