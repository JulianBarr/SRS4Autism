from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.kg_client import KnowledgeGraphClient, KnowledgeGraphQueryError
from backend.app.utils.oxigraph_utils import get_kg_store
from backend.database.db import get_db
from backend.app.models import ChildProfile, MilestoneProgress


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["survey"])

STATE_ACTION_TO_STATUS = {
    "PASS_NODE": "PASS",
    "FAIL": "FAIL",
    "FAIL_PROMPT_DEPENDENT": "PROMPT_DEPENDENT",
    "ASSUMED_MASTERED": "ASSUMED_MASTERED",
}

_CUMA_SURVEY = "http://cuma.ai/schema/survey/"
_VBMAPP = "http://cuma.ai/schema/vbmapp/"

_OPTION_ORDER = ("FAIL", "FAIL_PROMPT_DEPENDENT", "PASS_NODE")


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


class SurveyAnswerBody(BaseModel):
    question_uri: str = Field(..., description="URI of the ParentQuestion answered")
    stateAction: str = Field(..., description="Selected option state, e.g. FAIL, PASS_NODE")


@router.get("/survey/next")
def get_next_survey_question(
    lang: str = "en",  # Add language parameter with default "en"
    kg_client: KnowledgeGraphClient = Depends(get_kg_client),
    db: Session = Depends(get_db), # Add DB session dependency
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
        FILTER(LANG(?prompt_literal) = "{lang}")
        FILTER(LANG(?opt_literal) = "{lang}")
        
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve survey questions from knowledge graph"
        )

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

    # Get answered milestone URIs for the default child (Yiming)
    child_profile = db.query(ChildProfile).filter(ChildProfile.name == "Yiming").first()
    if not child_profile:
        logger.warning("Default child profile 'Yiming' not found for survey. Proceeding without filtering.")
        answered_milestone_uris = set()
    else:
        answered_milestone_uris = set(
            [mp.milestone_uri for mp in db.query(MilestoneProgress).filter(MilestoneProgress.child_id == child_profile.id).all()]
        )

    for q_uri, q_data in questions_map.items():
        # Query the milestone_uri for the current question_uri
        milestone_query = """
            PREFIX cuma-survey: <http://cuma.ai/schema/survey/>
            SELECT ?milestone_uri
            WHERE {{
                <{q_uri}> cuma-survey:evaluatesNode ?milestone_uri .
            }}
        """
        templated_milestone_query = milestone_query.format(q_uri=q_uri)
        milestone_results = kg_client.query_bindings(templated_milestone_query)
        associated_milestone_uri = None
        for row in milestone_results:
            associated_milestone_uri = _binding_str(row.get("milestone_uri"))
            break

        # Only add question if its associated milestone has not been answered
        if associated_milestone_uri and associated_milestone_uri not in answered_milestone_uris:
            q_data["options"] = _sort_options(q_data["options"])
            questions.append(q_data)

    # If there are still questions, sort them (e.g., by some priority) and return the first one
    # For now, just return the first available (unanswered) question.
    if questions:
        final_question = questions[0]
        print("========== [DEBUG] FINAL JSON PAYLOAD ==========")
        print(final_question)
        print("================================================")
        return final_question
    
    # Fallback to mock questions if no KG questions are found (if _pick_next_mock was defined)
    # For now, raise an error if no questions are found
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No survey questions found in knowledge graph"
    )


@router.post("/survey/answer")
async def post_survey_answer(
    body: SurveyAnswerBody,
    db: Session = Depends(get_db),
    kg_client: KnowledgeGraphClient = Depends(get_kg_client),
) -> dict[str, str]:
    # 1. Use SPARQL to query the milestone_uri for the given question_uri
    sparql_query = """
        PREFIX cuma-survey: <http://cuma.ai/schema/survey/>
        SELECT ?milestone_uri
        WHERE {
            <{{question_uri}}> cuma-survey:evaluatesNode ?milestone_uri .
        }
    """
    sparql_query_templated = sparql_query.replace("{{question_uri}}", body.question_uri)

    try:
        kg_results = kg_client.query_bindings(sparql_query_templated)
        milestone_uri = None
        for row in kg_results:
            milestone_uri = _binding_str(row.get("milestone_uri"))
            break  # Get the first milestone_uri found
        
        if not milestone_uri:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Milestone URI not found for question: {body.question_uri}"
            )

    except KnowledgeGraphQueryError as exc:
        logger.error("Failed to query knowledge graph for milestone URI: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve milestone information from knowledge graph"
        )
    
    # 2. Get the current Mock Child (Yiming)
    # In a real application, child_id would come from authentication or path parameter
    child_profile = db.query(ChildProfile).filter(ChildProfile.name == "Yiming").first()
    if not child_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default child profile 'Yiming' not found. Please ensure it's seeded."
        )
    child_id = child_profile.id

    # 3. Map stateAction to DB status
    db_status = STATE_ACTION_TO_STATUS.get(body.stateAction)
    if not db_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stateAction: {body.stateAction}"
        )
    
    # 4. Upsert MilestoneProgress
    try:
        milestone_progress = db.query(MilestoneProgress).filter(
            MilestoneProgress.child_id == child_id,
            MilestoneProgress.milestone_uri == milestone_uri
        ).first()

        if milestone_progress:
            # Update existing record
            milestone_progress.status = db_status
            milestone_progress.source = "SURVEY"  # Assuming all survey answers are from 'SURVEY'
            milestone_progress.created_at = func.now() # Manually update timestamp
        else:
            # Create new record
            milestone_progress = MilestoneProgress(
                child_id=child_id,
                milestone_uri=milestone_uri,
                status=db_status,
                source="SURVEY"
            )
            db.add(milestone_progress)
        
        db.commit()
        db.refresh(milestone_progress)
        logger.info(
            "MilestoneProgress upserted: Child ID %s, Milestone URI %s, Status %s",
            child_id,
            milestone_uri,
            db_status,
        )
        print(f"[survey] answer recorded in DB: {milestone_progress.milestone_uri} -> {milestone_progress.status}")

    except Exception as e:
        db.rollback()
        logger.error("Failed to upsert MilestoneProgress: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record survey answer in database"
        )

    return {"status": "success", "milestone_uri": milestone_uri, "recorded_status": db_status}