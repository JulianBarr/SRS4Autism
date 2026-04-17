from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.utils.oxigraph_utils import get_kg_store

router = APIRouter()

REQUIRES_PREREQUISITE = "http://cuma.ai/schema/requiresPrerequisite"
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


def _fetch_neighbor_edges(uri: str, direction: GraphDirection) -> list[tuple[str, str]]:
    clauses: list[str] = []
    if direction in {GraphDirection.forward, GraphDirection.both}:
        clauses.append(
            f"""
            {{
              BIND(<{uri}> AS ?source)
              ?source <{REQUIRES_PREREQUISITE}> ?target .
            }}
            """
        )
    if direction in {GraphDirection.backward, GraphDirection.both}:
        clauses.append(
            f"""
            {{
              BIND(<{uri}> AS ?target)
              ?source <{REQUIRES_PREREQUISITE}> ?target .
            }}
            """
        )

    if not clauses:
        return []

    query = f"""
    SELECT DISTINCT ?source ?target
    WHERE {{
      {' UNION '.join(clauses)}
    }}
    """
    rows = _run_query_bindings(query)
    edges: list[tuple[str, str]] = []
    for row in rows:
        source = _node_term_to_value(row.get("source"))
        target = _node_term_to_value(row.get("target"))
        if source and target:
            edges.append((source, target))
    return edges


def _fetch_labels(uris: set[str]) -> dict[str, str]:
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


@router.get("/subgraph")
async def get_subgraph(
    center_uri: str = Query(..., description="Center node URI"),
    max_hops: int = Query(2, ge=1, le=6, description="Max BFS hops"),
    direction: GraphDirection = Query(
        GraphDirection.both, description="Traversal direction: forward/backward/both"
    ),
) -> dict[str, object]:
    center_uri = center_uri.strip()
    if not center_uri.startswith("http://") and not center_uri.startswith("https://"):
        raise HTTPException(status_code=400, detail="center_uri must be an absolute URI")

    visited: set[str] = {center_uri}
    edges: set[tuple[str, str]] = set()
    queue: deque[tuple[str, int]] = deque([(center_uri, 0)])

    while queue:
        current_uri, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for source, target in _fetch_neighbor_edges(current_uri, direction):
            edges.add((source, target))
            if source not in visited:
                visited.add(source)
                queue.append((source, depth + 1))
            if target not in visited:
                visited.add(target)
                queue.append((target, depth + 1))

    labels = _fetch_labels(visited)

    nodes = [
        {
            "id": uri,
            "uri": uri,
            "label": labels.get(uri, uri.rsplit("/", 1)[-1]),
            "is_center": uri == center_uri,
        }
        for uri in sorted(visited)
    ]
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
