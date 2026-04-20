"""
Adaptive parent survey feed — SPARQL-backed next-question selection with mock fallback.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fastapi import Depends
from backend.database.kg_client import KnowledgeGraphClient, KnowledgeGraphQueryError
from backend.app.utils.oxigraph_utils import get_kg_store # Import get_kg_store


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["survey"])

# --- Session-local storage (replace with DB / profile-scoped store later) ---
_survey_answer_log: list[dict[str, Any]] = []
_answered_uris: set[str] = set()

_CUMA_SURVEY = "http://cuma.ai/schema/survey/"
_VBMAPP = "http://cuma.ai/schema/vbmapp/"

_OPTION_ORDER = ("FAIL", "FAIL_PROMPT_DEPENDENT", "PASS_NODE")

_MOCK_QUESTIONS: tuple[dict[str, Any], ...] = (
    {
        "question_uri": "http://cuma.ai/instance/survey/parent#mock_q1",
        "promptTemplate": (
            "Can {child_name} imitate a gross motor movement when you say "
            "\"Do this\"? /\n"
            "当你说「跟我做」时，{child_name}能模仿一个大动作吗？"
        ),
        "options": [
            {
                "option_uri": "http://cuma.ai/instance/survey/parent#mock_q1_opt_fail",
                "optionText": "Cannot do it / 无法完成",
                "stateAction": "FAIL",
            },
            {
                "option_uri": "http://cuma.ai/instance/survey/parent#mock_q1_opt_prompt",
                "optionText": "Needs prompts / 需提示",
                "stateAction": "FAIL_PROMPT_DEPENDENT",
            },
            {
                "option_uri": "http://cuma.ai/instance/survey/parent#mock_q1_opt_pass",
                "optionText": "Does it independently / 独立完成",
                "stateAction": "PASS_NODE",
            },
        ],
        "source": "mock",
    },
    {
        "question_uri": "http://cuma.ai/instance/survey/parent#mock_q2",
        "promptTemplate": (
            "Does {child_name} make eye contact when you call their name? /\n"
            "当你叫{child_name}的名字时，他/她会看你吗？"
        ),
        "options": [
            {
                "option_uri": "http://cuma.ai/instance/survey/parent#mock_q2_opt_fail",
                "optionText": "Cannot do it / 无法完成",
                "stateAction": "FAIL",
            },
            {
                "option_uri": "http://cuma.ai/instance/survey/parent#mock_q2_opt_prompt",
                "optionText": "Needs prompts / 需提示",
                "stateAction": "FAIL_PROMPT_DEPENDENT",
            },
            {
                "option_uri": "http://cuma.ai/instance/survey/parent#mock_q2_opt_pass",
                "optionText": "Does it independently / 独立完成",
                "stateAction": "PASS_NODE",
            },
        ],
        "source": "mock",
    },
)


def _fill_prompt_template(text: str, child_label: str = "宝宝") -> str:
    return (
        text.replace("{{child_name}}", child_label)
        .replace("{child_name}", child_label)
        .replace("{{pronoun}}", "他")
        .replace("{pronoun}", "他")
    )


def _localize_bilingual_text(text: str, lang: str) -> str:
    """Split legacy bilingual mock text and return one locale."""
    if "/" not in text:
        return text
    left, right = text.split("/", 1)
    if lang == "zh":
        return right.strip()
    return left.strip()


def _binding_str(term: Optional[dict[str, Any]]) -> str:
    if not term:
        return ""
    if term.get("type") == "uri":
        return str(term.get("value", ""))
    return str(term.get("value", ""))


def _binding_bool(term: Optional[dict[str, Any]]) -> bool:
    if not term:
        return False
    v = str(term.get("value", "")).lower()
    return v in ("true", "1")


def _state_action_key(term: Optional[dict[str, Any]]) -> str:
    """Normalize stateAction to a short string for sorting / API."""
    if not term:
        return ""
    if term.get("type") == "uri":
        uri = str(term.get("value", ""))
        if uri.rstrip("/").endswith("FAIL"):
            return "FAIL"
        if "PROMPT" in uri or "DEPENDENT" in uri:
            return "FAIL_PROMPT_DEPENDENT"
        if "PASS" in uri:
            return "PASS_NODE"
        return uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return str(term.get("value", ""))


def _sort_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank = {k: i for i, k in enumerate(_OPTION_ORDER)}

    def key(o: dict[str, Any]) -> tuple[int, str]:
        sa = o.get("stateAction") or ""
        return (rank.get(sa, 99), sa)

    return sorted(options, key=key)


def get_kg_client() -> KnowledgeGraphClient:
    return KnowledgeGraphClient(endpoint_url="oxigraph://embedded")

# ... (rest of the file)





def _pick_next_mock(lang: str = "en") -> dict[str, Any]:
    """Rotate through mock questions; when all are answered, clear and repeat."""
    mock_uris = {m["question_uri"] for m in _MOCK_QUESTIONS}
    unanswered = [m for m in _MOCK_QUESTIONS if m["question_uri"] not in _answered_uris]
    if not unanswered:
        _answered_uris.difference_update(mock_uris)
        unanswered = list(_MOCK_QUESTIONS)
    chosen = unanswered[0]
    localized_options = [
        {
            "option_uri": opt["option_uri"],
            "optionText": _localize_bilingual_text(opt["optionText"], lang),
            "stateAction": opt["stateAction"],
        }
        for opt in chosen["options"]
    ]
    return {
        "question_uri": chosen["question_uri"],
        "promptTemplate": _fill_prompt_template(
            _localize_bilingual_text(chosen["promptTemplate"], lang)
        ),
        "options": localized_options,
        "source": chosen["source"],
    }


class SurveyAnswerBody(BaseModel):
    question_uri: str = Field(..., description="URI of the ParentQuestion answered")
    stateAction: str = Field(..., description="Selected option state, e.g. FAIL, PASS_NODE")


@router.get("/survey/next")
def get_next_survey_question(
    lang: str = "en",  # Add language parameter with default "en"
    kg_client: KnowledgeGraphClient = Depends(get_kg_client),
) -> dict[str, Any]:
    """
    Next ParentQuestion from KG (level-1 milestones; bottleneck first), excluding session answers.
    Falls back to built-in mock pairs when the graph has no matching data.
    """
    sparql_query = """
    PREFIX cuma-survey: <http://cuma.ai/schema/survey/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT DISTINCT ?q_uri ?promptText ?opt_uri ?optText ?stateAction
    WHERE {{
        ?q_uri a cuma-survey:ParentQuestion ;
               cuma-survey:promptTemplate ?prompt_literal ;
               cuma-survey:hasOption ?opt_uri .
        ?opt_uri cuma-survey:optionText ?opt_literal ;
                 cuma-survey:stateAction ?stateAction .

        # Force language filtering based on request
        FILTER(LANG(?prompt_literal) = "{{lang}}")
        FILTER(LANG(?opt_literal) = "{{lang}}")
        
        BIND(STR(?prompt_literal) AS ?promptText)
        BIND(STR(?opt_literal) AS ?optText)
    }}
    """
    
    # Normalize language tag for RDF filter
    normalized_lang = "zh" if lang.lower() in ["cn", "zh"] else "en"

    sparql_query_templated = sparql_query.format(lang=normalized_lang)

    print("========== [DEBUG] EXECUTING SPARQL ==========")
    print(sparql_query_templated)
    print("==============================================")

    try:
        results = kg_client.query_bindings(sparql_query_templated)
        print("========== [DEBUG] RAW DB RESULTS (First 10) ==========")
        # Convert results to a list to iterate multiple times if needed for debugging
        results_list = list(results)
        for idx, row in enumerate(results_list):
            if idx >= 10:
                break
            print(row)
        print("=======================================================")
    except KnowledgeGraphQueryError as exc:
        logger.error("Failed to query knowledge graph for survey questions: %s", exc)
        return _pick_next_mock(normalized_lang)

    questions_map: dict[str, dict[str, Any]] = {}

    for row in results_list:
        q_uri = _binding_str(row.get("q_uri"))
        opt_uri = _binding_str(row.get("opt_uri"))

        if not q_uri or not opt_uri:
            continue

        if q_uri not in questions_map:
            questions_map[q_uri] = {
                "question_uri": q_uri,
                "promptTemplate": _fill_prompt_template(_binding_str(row.get("promptText"))),
                "options": [],
                "source": "kg",
            }
        
        # Add option, only if not already added.
        # Given language filter, there should only be one optionText per opt_uri.
        option_exists = any(
            opt.get("option_uri") == opt_uri for opt in questions_map[q_uri]["options"]
        )
        if not option_exists:
            questions_map[q_uri]["options"].append(
                {
                    "option_uri": opt_uri,
                    "optionText": _binding_str(row.get("optText")),
                    "stateAction": _state_action_key(row.get("stateAction")),
                }
            )
            
    # Convert dictionary to a list of questions and sort options
    questions = []
    for q_uri, q_data in questions_map.items():
        if q_uri in _answered_uris:
            continue
        q_data["options"] = _sort_options(q_data["options"])
        questions.append(q_data)

    if questions:
        final_question = questions[0]
        print("========== [DEBUG] FINAL JSON PAYLOAD ==========")
        print(final_question)
        print("================================================")
        return final_question
    
    # Fallback to mock questions if no KG questions are found
    return _pick_next_mock(normalized_lang)


@router.post("/survey/answer")
def post_survey_answer(body: SurveyAnswerBody) -> dict[str, str]:
    _answered_uris.add(body.question_uri)
    entry = {
        "question_uri": body.question_uri,
        "stateAction": body.stateAction,
    }
    _survey_answer_log.append(entry)
    logger.info("survey answer recorded: %s", entry)
    print(f"[survey] answer: {entry}")
    return {"status": "success"}
