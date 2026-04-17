#!/usr/bin/env python3
"""
Weave intra-domain linear and cross-domain prerequisite edges into the VB-MAPP ontology graph.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

VBMAPP_SCHEMA = Namespace("http://cuma.ai/schema/vbmapp/")
VBMAPP_INST = Namespace("http://cuma.ai/instance/vbmapp/")

# Milestone index in URI local name, e.g. tact_10_m -> 10
_MILESTONE_INDEX_RE = re.compile(r"_(\d+)_m(?:\b|$)")

# Cross-domain: subject local name -> prerequisite local names
CROSS_DOMAIN_PREREQS: dict[str, list[str]] = {
    "lrffc_6_m": ["tact_5_m", "listener_5_m"],
    "intraverbal_6_m": ["tact_5_m", "listener_5_m", "echoic_5_m"],
    "reading_11_m": ["tact_10_m", "listener_10_m", "vp_mts_10_m"],
    "math_11_m": ["tact_10_m", "listener_10_m", "vp_mts_10_m"],
    "writing_12_m": ["motor_imitation_10_m", "vp_mts_10_m"],
}


def _milestone_index(uri: URIRef) -> int | None:
    m = _MILESTONE_INDEX_RE.search(str(uri))
    if not m:
        return None
    return int(m.group(1))


def _node_in_graph(g: Graph, uri: URIRef) -> bool:
    return any(g.triples((uri, None, None))) or any(g.triples((None, None, uri)))


def weave_intra_domain(g: Graph) -> int:
    """Within each domainName, chain milestones by index: N requiresPrerequisite N-1."""
    by_domain: dict[str, list[tuple[int, URIRef]]] = defaultdict(list)

    for ms in g.subjects(RDF.type, VBMAPP_SCHEMA.Milestone):
        if not isinstance(ms, URIRef):
            continue
        domain_lit = g.value(ms, VBMAPP_SCHEMA.domainName)
        if domain_lit is None:
            continue
        domain_name = str(domain_lit)
        idx = _milestone_index(ms)
        if idx is None:
            continue
        by_domain[domain_name].append((idx, ms))

    added = 0
    for _domain, items in by_domain.items():
        items.sort(key=lambda x: x[0])
        for i in range(1, len(items)):
            _prev_idx, prev_ms = items[i - 1]
            _cur_idx, cur_ms = items[i]
            if (cur_ms, VBMAPP_SCHEMA.requiresPrerequisite, prev_ms) in g:
                continue
            g.add((cur_ms, VBMAPP_SCHEMA.requiresPrerequisite, prev_ms))
            added += 1

    return added


def weave_cross_domain(g: Graph) -> int:
    added = 0
    for subject_local, prereq_locals in CROSS_DOMAIN_PREREQS.items():
        subj = VBMAPP_INST[subject_local]
        if not _node_in_graph(g, subj):
            continue
        for pl in prereq_locals:
            prereq = VBMAPP_INST[pl]
            if not _node_in_graph(g, prereq):
                continue
            if (subj, VBMAPP_SCHEMA.requiresPrerequisite, prereq) in g:
                continue
            g.add((subj, VBMAPP_SCHEMA.requiresPrerequisite, prereq))
            added += 1
    return added


def main() -> None:
    base = Path.cwd()
    input_path = base / "vbmapp_full_ontology.ttl"
    output_path = base / "vbmapp_woven_ontology.ttl"

    g = Graph()
    g.bind("vbmapp-schema", VBMAPP_SCHEMA)
    g.bind("vbmapp-inst", VBMAPP_INST)
    g.parse(input_path, format="turtle")

    intra_added = weave_intra_domain(g)
    cross_added = weave_cross_domain(g)

    g.serialize(destination=output_path, format="turtle")

    print(f"成功添加同领域（Intra-domain）连线: {intra_added} 条")
    print(f"成功添加跨领域（Cross-domain）连线: {cross_added} 条")


if __name__ == "__main__":
    main()
