from __future__ import annotations

import json
import logging
from typing import Any

import pyoxigraph as oxigraph
from fastapi import APIRouter, HTTPException, Request, Response

from app.utils.oxigraph_utils import get_kg_store

logger = logging.getLogger(__name__)

router = APIRouter()


def _term_to_sparql_json(term: Any) -> dict[str, str]:
    """Convert an Oxigraph term to SPARQL JSON binding format."""
    if isinstance(term, oxigraph.NamedNode):
        return {"type": "uri", "value": str(term.value)}
    if isinstance(term, oxigraph.Literal):
        result = {"type": "literal", "value": str(term.value)}
        if term.language:
            result["xml:lang"] = term.language
        elif term.datatype and str(term.datatype.value) != "http://www.w3.org/2001/XMLSchema#string":
            result["datatype"] = str(term.datatype.value)
        return result
    if isinstance(term, oxigraph.BlankNode):
        return {"type": "bnode", "value": str(term.value)}
    return {"type": "literal", "value": str(term)}


@router.post("/query")
async def query_kg(request: Request) -> Response:
    """
    Execute raw SPARQL text against the Oxigraph store and return SPARQL JSON.
    """
    query_text = (await request.body()).decode("utf-8").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Request body must contain SPARQL query text.")

    try:
        logger.info("Received SPARQL query:\n%s", query_text)
        raw_results = get_kg_store().query(query_text)

        if isinstance(raw_results, bool):
            payload: dict[str, Any] = {"boolean": raw_results}
        elif hasattr(raw_results, "__bool__") and not hasattr(raw_results, "variables"):
            payload = {"boolean": bool(raw_results)}
        else:
            variables = [var.value for var in raw_results.variables]
            bindings: list[dict[str, dict[str, str]]] = []

            for solution in raw_results:
                row: dict[str, dict[str, str]] = {}
                for var_name in variables:
                    try:
                        term = solution[var_name]
                    except (KeyError, TypeError):
                        continue
                    if term is not None:
                        row[var_name] = _term_to_sparql_json(term)
                bindings.append(row)

            payload = {
                "head": {"vars": variables},
                "results": {"bindings": bindings},
            }
            if not bindings:
                logger.info("SPARQL query executed successfully but returned no bindings.")

        return Response(
            content=json.dumps(payload, ensure_ascii=False),
            media_type="application/sparql-results+json",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("SPARQL query failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"SPARQL query failed: {exc}") from exc


@router.get("/inspect")
async def inspect_kg_store() -> dict[str, Any]:
    """
    Return a small sample of raw triples from the current KG store.
    """
    inspect_query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 20"
    try:
        raw_results = get_kg_store().query(inspect_query)
        variables = [var.value for var in raw_results.variables]
        bindings: list[dict[str, dict[str, str]]] = []

        for solution in raw_results:
            row: dict[str, dict[str, str]] = {}
            for var_name in variables:
                try:
                    term = solution[var_name]
                except (KeyError, TypeError):
                    continue
                if term is not None:
                    row[var_name] = _term_to_sparql_json(term)
            bindings.append(row)

        if not bindings:
            logger.info("KG inspect probe returned no triples for query: %s", inspect_query)

        return {
            "head": {"vars": variables},
            "results": {"bindings": bindings},
        }
    except Exception as exc:
        logger.error("KG inspect probe failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"KG inspect probe failed: {exc}") from exc
