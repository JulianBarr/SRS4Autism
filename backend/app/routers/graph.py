from __future__ import annotations

from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from rdflib import Namespace

from app.utils.oxigraph_utils import get_kg_store

router = APIRouter()

VBMAPP_SCHEMA = Namespace("http://cuma.ai/schema/vbmapp/")
REQUIRES_PREREQUISITE = str(VBMAPP_SCHEMA.requiresPrerequisite)
VBMAPP_DESCRIPTION = str(VBMAPP_SCHEMA.description)
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"


class GraphDirection(str, Enum):
    forward = "forward"
    backward = "backward"
    both = "both"


def _node_term_to_value(term: dict[str, str] | None) -> Optional[str]:
    if not term:
        return None
    return term.get("value")


def _run_query_bindings(query: str) -> list[dict[str, dict[str, str]]]:
    raw_results = get_kg_store().query(query)
    variables = [var.value for var in raw_results.variables]
    bindings: list[dict[str, dict[str, str]]] = []
    for solution in raw_results:
        row: dict[str, dict[str, str]] = {}
        for var_name in variables:
            try:
                value = solution[var_name]
            except (KeyError, TypeError):
                continue
            if value is None:
                continue
            if hasattr(value, "value"):
                term_type = "uri"
                if value.__class__.__name__ == "Literal":
                    term_type = "literal"
                row[var_name] = {"type": term_type, "value": str(value.value)}
        bindings.append(row)
    return bindings


def _build_property_path(direction: GraphDirection) -> str:
    predicate = f"<{REQUIRES_PREREQUISITE}>"
    if direction == GraphDirection.forward:
        return predicate
    if direction == GraphDirection.backward:
        return f"^{predicate}"
    return f"({predicate}|^{predicate})"


def _fetch_reachable_nodes(center_uri: str, direction: GraphDirection, max_hops: int) -> set[str]:
    path_step = _build_property_path(direction)
    hop_clauses = []
    for hop in range(1, max_hops + 1):
        path_expr = "/".join(path_step for _ in range(hop))
        hop_clauses.append(f"{{ ?center {path_expr} ?node . }}")
    hop_union = "\n      UNION\n      ".join(hop_clauses)
    query = f"""
    SELECT DISTINCT ?node
    WHERE {{
      BIND(<{center_uri}> AS ?center)
      {{
        BIND(?center AS ?node)
      }}
      UNION
      {hop_union}
    }}
    """
    rows = _run_query_bindings(query)
    nodes: set[str] = set()
    for row in rows:
        node = _node_term_to_value(row.get("node"))
        if node:
            nodes.add(node)
    return nodes


def _fetch_edges_within_nodes(node_uris: set[str]) -> set[tuple[str, str]]:
    if not node_uris:
        return set()
    values = " ".join(f"<{uri}>" for uri in sorted(node_uris))
    query = f"""
    SELECT DISTINCT ?source ?target
    WHERE {{
      VALUES ?source {{ {values} }}
      VALUES ?target {{ {values} }}
      ?source <{REQUIRES_PREREQUISITE}> ?target .
    }}
    """
    rows = _run_query_bindings(query)
    edges: set[tuple[str, str]] = set()
    for row in rows:
        source = _node_term_to_value(row.get("source"))
        target = _node_term_to_value(row.get("target"))
        if source and target:
            edges.add((source, target))
    return edges


# Prefer English-tagged (or untagged) literals for default `label`; Chinese variants use `label_zh`.
_EN_LANG_FILTER = (
    'FILTER(LANG(?labelLit) IN ("en", "en-US") || LANG(?labelLit) = "")'
)
_ZH_LANG_FILTER = (
    'FILTER(LANG(?labelLit) IN ("zh", "zh-CN", "zh-Hans", "zh-Hant"))'
)

_DESC_EN_LANG_FILTER = (
    'FILTER(LANG(?descLit) IN ("en", "en-US") || LANG(?descLit) = "")'
)
_DESC_ZH_LANG_FILTER = (
    'FILTER(LANG(?descLit) IN ("zh", "zh-CN", "zh-Hans", "zh-Hant"))'
)


def _fetch_labels_any(uris: set[str]) -> dict[str, str]:
    """One arbitrary rdfs:label per node (fallback when language-specific query misses)."""
    if not uris:
        return {}
    values = " ".join(f"<{uri}>" for uri in sorted(uris))
    query = f"""
    SELECT ?node (SAMPLE(?labelLit) AS ?label)
    WHERE {{
      VALUES ?node {{ {values} }}
      OPTIONAL {{
        ?node <{RDFS_LABEL}> ?labelLit .
      }}
    }}
    GROUP BY ?node
    """
    rows = _run_query_bindings(query)
    labels: dict[str, str] = {}
    for row in rows:
        node_uri = _node_term_to_value(row.get("node"))
        label = _node_term_to_value(row.get("label"))
        if node_uri:
            labels[node_uri] = label or node_uri.rsplit("/", 1)[-1]
    return labels


def _fetch_labels_with_lang_filter(uris: set[str], lang_filter: str) -> dict[str, str]:
    """rdfs:labels matching the given LANG() filter (one SAMPLE per node)."""
    if not uris:
        return {}
    values = " ".join(f"<{uri}>" for uri in sorted(uris))
    query = f"""
    SELECT ?node (SAMPLE(?labelLit) AS ?label)
    WHERE {{
      VALUES ?node {{ {values} }}
      ?node <{RDFS_LABEL}> ?labelLit .
      {lang_filter}
    }}
    GROUP BY ?node
    """
    rows = _run_query_bindings(query)
    labels: dict[str, str] = {}
    for row in rows:
        node_uri = _node_term_to_value(row.get("node"))
        label = _node_term_to_value(row.get("label"))
        if node_uri and label:
            labels[node_uri] = label
    return labels


def _fetch_vbmapp_descriptions_with_lang_filter(uris: set[str], lang_filter: str) -> dict[str, str]:
    """vbmapp:description literals matching the given LANG() filter (one SAMPLE per node)."""
    if not uris:
        return {}
    values = " ".join(f"<{uri}>" for uri in sorted(uris))
    query = f"""
    SELECT ?node (SAMPLE(?descLit) AS ?desc)
    WHERE {{
      VALUES ?node {{ {values} }}
      ?node <{VBMAPP_DESCRIPTION}> ?descLit .
      {lang_filter}
    }}
    GROUP BY ?node
    """
    rows = _run_query_bindings(query)
    out: dict[str, str] = {}
    for row in rows:
        node_uri = _node_term_to_value(row.get("node"))
        desc = _node_term_to_value(row.get("desc"))
        if node_uri and desc:
            out[node_uri] = desc
    return out


@router.get("/subgraph")
async def get_subgraph(
    center_uri: str = Query(..., description="Center node URI"),
    max_hops: int = Query(2, ge=1, le=6, description="Max traversal hops"),
    direction: GraphDirection = Query(
        GraphDirection.both, description="Traversal direction: forward/backward/both"
    ),
) -> dict[str, object]:
    center_uri = center_uri.strip()
    if not center_uri.startswith("http://") and not center_uri.startswith("https://"):
        raise HTTPException(status_code=400, detail="center_uri must be an absolute URI")

    visited = _fetch_reachable_nodes(center_uri, direction, max_hops)
    edges = _fetch_edges_within_nodes(visited)

    labels_en = _fetch_labels_with_lang_filter(visited, _EN_LANG_FILTER)
    labels_zh = _fetch_labels_with_lang_filter(visited, _ZH_LANG_FILTER)
    labels_any = _fetch_labels_any(visited)
    descriptions_en = _fetch_vbmapp_descriptions_with_lang_filter(visited, _DESC_EN_LANG_FILTER)
    descriptions_zh = _fetch_vbmapp_descriptions_with_lang_filter(visited, _DESC_ZH_LANG_FILTER)

    nodes = []
    for uri in sorted(visited):
        slug = uri.rsplit("/", 1)[-1]
        label = labels_en.get(uri) or labels_zh.get(uri) or labels_any.get(uri, slug)
        label_zh = labels_zh.get(uri)
        nodes.append(
            {
                "id": uri,
                "uri": uri,
                "label": label,
                "label_zh": label_zh,
                "description_en": descriptions_en.get(uri),
                "description_zh": descriptions_zh.get(uri),
                "is_center": uri == center_uri,
            }
        )
    links = [
        {
            "source": source,
            "target": target,
            "predicate": REQUIRES_PREREQUISITE,
        }
        for source, target in sorted(edges)
    ]
    return {
        "center_uri": center_uri,
        "max_hops": max_hops,
        "direction": direction.value,
        "nodes": nodes,
        "links": links,
    }


@router.get("/nodes")
async def search_graph_nodes(
    q: str = Query("", description="Keyword for URI/label lookup"),
    limit: int = Query(20, ge=1, le=50),
) -> dict[str, object]:
    normalized_q = q.strip().lower()
    q_filter = ""
    if normalized_q:
        escaped = normalized_q.replace('"', '\\"')
        q_filter = (
            f'FILTER(CONTAINS(LCASE(STR(?uri)), "{escaped}") '
            f'|| CONTAINS(LCASE(STR(?label)), "{escaped}"))'
        )
    query = f"""
    SELECT DISTINCT ?uri (SAMPLE(?labelLit) AS ?label)
    WHERE {{
      ?uri <{REQUIRES_PREREQUISITE}> ?any .
      OPTIONAL {{ ?uri <{RDFS_LABEL}> ?labelLit . }}
      BIND(COALESCE(?labelLit, STR(?uri)) AS ?label)
      {q_filter}
    }}
    GROUP BY ?uri
    LIMIT {limit}
    """
    rows = _run_query_bindings(query)
    items = []
    for row in rows:
        uri = _node_term_to_value(row.get("uri"))
        label = _node_term_to_value(row.get("label"))
        if uri:
            items.append(
                {
                    "uri": uri,
                    "label": label or uri.rsplit("/", 1)[-1],
                }
            )
    return {"items": items}
