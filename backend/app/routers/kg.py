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


@router.get("/cognition-macro-structure")
async def get_cognition_macro_structure():
    """
    Get macro structure (MacroObjective by age bracket and module) from quest_full.ttl in Oxigraph.
    Returns Age -> Module -> Macro hierarchy. Deduplicates by macroLabel (merge tasks from same-named nodes).
    Used by CognitionContentManager / Quest Library. Falls back to empty if KG not loaded.
    """
    try:
        from database.kg_client import KnowledgeGraphClient
        client = KnowledgeGraphClient()
        sparql = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ecta-kg: <http://ecta.ai/schema/>
        PREFIX ecta-inst: <http://ecta.ai/instance/>

        SELECT ?macro ?macroLabel ?ageBracket ?module ?phase ?phaseLabel ?phaseMaterial
               ?teachingSteps ?groupClassGeneralization ?homeGeneralization
        WHERE {
            ?macro a ecta-kg:MacroObjective ;
                   rdfs:label ?macroLabel .
            OPTIONAL { ?macro ecta-kg:belongsToModule ?module . }
            OPTIONAL { ?macro ecta-kg:recommendedAgeBracket ?ageBracket . }
            OPTIONAL {
                ?macro ecta-kg:hasPhase ?phase .
                ?phase rdfs:label ?phaseLabel .
                OPTIONAL { ?phase ecta-kg:suggestedMaterials ?phaseMaterial . }
                OPTIONAL { ?phase ecta-kg:teachingSteps ?teachingSteps . }
                OPTIONAL { ?phase ecta-kg:groupClassGeneralization ?groupClassGeneralization . }
                OPTIONAL { ?phase ecta-kg:homeGeneralization ?homeGeneralization . }
            }
        }
        ORDER BY ?module ?ageBracket ?macro ?phase
        """
        bindings = client.query_bindings(sparql)
        if not bindings:
            return {"data": [], "source": "kg_empty"}

        from collections import defaultdict
        UNCATEGORIZED_MODULE = "未分类"
        UNCATEGORIZED_AGE = "未分类年龄段"
        age_display = {"3-12个月": "3-12个月", "1-2岁": "1-2岁", "2-3岁": "2-3岁", "3-4岁": "3-4岁", "default": UNCATEGORIZED_AGE}
        module_order = ["认知发展篇", "语言表达篇", "语言理解篇", "小肌肉发展篇", "大肌肉发展篇", "模仿发展篇", UNCATEGORIZED_MODULE]

        # age_short -> module_name -> macro_label_normalized -> { label, tasks }
        # Dedupe by macroLabel: same label = merge tasks
        by_age_module_macro = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"label": "", "tasks": []})))

        for row in bindings:
            macro_uri = row.get("macro", {}).get("value", "")
            uri_id = macro_uri.split("/")[-1] if "/" in macro_uri else macro_uri
            macro_label_raw = row.get("macroLabel", {}).get("value", uri_id)
            macro_label = (macro_label_raw or "").strip()
            macro_key = macro_label or uri_id  # normalize for dedup
            module_val = row.get("module", {}).get("value", "")
            module_name = module_val.strip() if module_val and isinstance(module_val, str) else UNCATEGORIZED_MODULE
            age = row.get("ageBracket", {}).get("value", "default")
            age_short = age.split("/")[-1] if age and "/" in age else (age or "default")
            phase_uri = row.get("phase", {}).get("value") if row.get("phase") else None
            phase_label = row.get("phaseLabel", {}).get("value", "") if row.get("phaseLabel") else ""
            phase_mat = row.get("phaseMaterial", {}).get("value", "") if row.get("phaseMaterial") else ""
            teaching_steps = row.get("teachingSteps", {}).get("value", "") if row.get("teachingSteps") else ""
            group_class_gen = row.get("groupClassGeneralization", {}).get("value", "") if row.get("groupClassGeneralization") else ""
            home_gen = row.get("homeGeneralization", {}).get("value", "") if row.get("homeGeneralization") else ""

            m = by_age_module_macro[age_short][module_name][macro_key]
            m["label"] = macro_label or uri_id
            if phase_uri and phase_label:
                phase_id = phase_uri.split("/")[-1] if "/" in phase_uri else phase_uri
                steps_list = []
                if teaching_steps and isinstance(teaching_steps, str):
                    steps_list = [s.strip() for s in teaching_steps.split("\n") if s.strip()]
                group_social = [group_class_gen] if (group_class_gen and isinstance(group_class_gen, str) and group_class_gen.strip()) else []
                home_natural = [home_gen] if (home_gen and isinstance(home_gen, str) and home_gen.strip()) else []
                environments = {
                    "structured_desktop": {"steps": steps_list},
                    "group_social": group_social,
                    "home_natural": home_natural,
                }
                phase_obj = {
                    "uri_id": f"ecta-inst:{phase_id}",
                    "title": phase_label,
                    "materials": [phase_mat] if phase_mat else [],
                    "environments": environments,
                }
                if not any(p["uri_id"] == phase_obj["uri_id"] for p in m["tasks"]):
                    m["tasks"].append(phase_obj)

        # Build result: Age -> Module -> Macro (reversed hierarchy)
        age_order = ["3-12个月", "1-2岁", "2-3岁", "3-4岁", "default"]
        result = []

        def build_modules_for_age(age_key):
            modules_data = []
            for mod_name in module_order:
                if mod_name not in by_age_module_macro[age_key]:
                    continue
                macros_list = [
                    {"macroLabel": d["label"], "tasks": d["tasks"]}
                    for d in by_age_module_macro[age_key][mod_name].values()
                ]
                modules_data.append({"moduleName": mod_name, "macros": macros_list})
            for mod_name in sorted(by_age_module_macro[age_key].keys()):
                if mod_name in module_order:
                    continue
                macros_list = [
                    {"macroLabel": d["label"], "tasks": d["tasks"]}
                    for d in by_age_module_macro[age_key][mod_name].values()
                ]
                modules_data.append({"moduleName": mod_name, "macros": macros_list})
            return modules_data

        for age_key in age_order:
            if age_key not in by_age_module_macro:
                continue
            modules_data = build_modules_for_age(age_key)
            if modules_data:
                result.append({
                    "ageBracket": age_display.get(age_key, age_key),
                    "modules": modules_data,
                })
        for age_key in sorted(by_age_module_macro.keys()):
            if age_key in age_order:
                continue
            modules_data = build_modules_for_age(age_key)
            if modules_data:
                result.append({
                    "ageBracket": age_display.get(age_key, age_key),
                    "modules": modules_data,
                })
        return {"data": result, "source": "kg"}
    except Exception as e:
        logger.warning(f"Cognition macro structure from KG failed: {e}")
        return {"data": [], "source": "error", "error": str(e)}
