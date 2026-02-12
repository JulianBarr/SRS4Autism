"""
KG (Knowledge Graph) router - grammar recommendations and related endpoints.
Restored from main.py refactor; provides grammar recommendations with KG/LLM/static fallback.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json
import logging
import os

from database.db import get_db
from database.services import ProfileService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter()


class GrammarRecommendationRequest(BaseModel):
    """Request body for grammar recommendations - matches frontend (LanguageContentManager, ProfileManager)."""
    mastered_grammar: Optional[List[str]] = None
    profile_id: str
    language: str = "zh"


def _to_frontend_format(rec: dict) -> dict:
    """Convert recommendation to format expected by frontend (gp_uri, grammar_point, structure)."""
    node_id = rec.get("node_id", "")
    label = rec.get("label", "")
    return {
        "gp_uri": node_id,
        "grammar_point": label,
        "grammar_point_zh": label if rec.get("language") == "zh" else "",
        "structure": rec.get("prerequisites", []) and f"Prereqs: {', '.join(rec['prerequisites'][:3])}" or "",
    }


@router.post("/grammar-recommendations")
async def get_grammar_recommendations(
    request: GrammarRecommendationRequest,
    db: Session = Depends(get_db),
):
    """
    Get grammar recommendations for a profile.
    Uses KG via IntegratedRecommenderService when available;
    falls back to LLM inference or static list.
    """
    try:
        logger.info(
            f"📚 KG grammar-recommendations: profile={request.profile_id}, lang={request.language}"
        )

        # 1. Try IntegratedRecommenderService (KG-backed)
        try:
            profile = ProfileService.get_by_id(db, request.profile_id)
            if profile:
                from services.integrated_recommender_service import (
                    IntegratedRecommenderService,
                )

                recommender = IntegratedRecommenderService(profile, db)
                all_recs = recommender.get_recommendations(
                    language=request.language,
                    mastered_words=None,
                )
                grammar_recs = [r for r in all_recs if r.content_type == "grammar"]
                if grammar_recs:
                    rec_dicts = [
                        {
                            "node_id": r.node_id,
                            "label": r.label,
                            "language": r.language,
                            "prerequisites": r.prerequisites or [],
                        }
                        for r in grammar_recs
                    ]
                    result = [_to_frontend_format(r) for r in rec_dicts]
                    return {
                        "recommendations": result,
                        "source": "kg_integrated",
                    }
        except Exception as e:
            logger.warning(f"IntegratedRecommenderService failed: {e}")

        # 2. LLM fallback: dynamic grammar recommendations
        try:
            from ..services.agent_service import AgentService

            api_key = AgentService._get_valid_api_key(None, "google")
            if api_key:
                lang_label = "Chinese" if request.language == "zh" else "English"
                system_prompt = f"""
You are a Knowledge Graph engine for a language learning app.
The user is learning {lang_label} grammar.
Return exactly {5} related grammar points that represent PREREQUISITES or EXTENSIONS for learners.
Return ONLY a JSON array, no other text:
[
  {{"topic": "Grammar Point 1", "reason": "Prerequisite"}},
  {{"topic": "Grammar Point 2", "reason": "Extension"}}
]
"""
                response = AgentService._call_llm(
                    system_prompt, api_key, "google", "gemini-2.0-flash"
                )
                if response and response != "[]":
                    clean = response.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(clean)
                    result = [
                        {
                            "gp_uri": f"grammar-{request.language}-{i}",
                            "grammar_point": p.get("topic", "Unknown"),
                            "grammar_point_zh": p.get("topic", ""),
                            "structure": p.get("reason", ""),
                        }
                        for i, p in enumerate(parsed) if isinstance(p, dict)
                    ]
                    return {
                        "recommendations": result,
                        "source": "ai_inference",
                    }
        except Exception as e:
            logger.warning(f"LLM fallback failed: {e}")

        # 3. Static fallback
        if request.language == "zh":
            fallback = [
                {"gp_uri": "grammar-zh-basic", "grammar_point": "基本句型", "grammar_point_zh": "基本句型", "structure": "Fundamental"},
                {"gp_uri": "grammar-zh-ma", "grammar_point": "吗 Questions", "grammar_point_zh": "吗字疑问句", "structure": "Fundamental"},
                {"gp_uri": "grammar-zh-le", "grammar_point": "了 (Perfective)", "grammar_point_zh": "了（完成体）", "structure": "Extension"},
            ]
        else:
            fallback = [
                {"gp_uri": "grammar-en-basic", "grammar_point": "Basic Sentence Structure", "grammar_point_zh": "", "structure": "Fundamental"},
                {"gp_uri": "grammar-en-yn", "grammar_point": "Yes/No Questions", "grammar_point_zh": "", "structure": "Fundamental"},
                {"gp_uri": "grammar-en-plural", "grammar_point": "Plural -s", "grammar_point_zh": "", "structure": "Extension"},
            ]
        return {
            "recommendations": fallback,
            "source": "static",
            "status": "fallback",
        }

    except Exception as e:
        logger.error(f"❌ KG grammar-recommendations error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
