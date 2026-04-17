#!/usr/bin/env python3
"""
Enrich Heep Hong Society (HHS) Turtle files with structured age, module, and clean labels.

Reads the six domain TTL files (e.g. 21_lang_debug.ttl), walks each hhs-inst:Task (and optionally
ontology Goal nodes for backward compatibility), adds cuma-schema triples, and writes *_enriched.ttl.

Run from project root with venv activated:
  python scripts/enrich_hhs_ttl.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# --- Namespaces (per project conventions) ---
CUMA_SCHEMA = Namespace("http://cuma.ai/schema/")
HHS_INST = Namespace("http://cuma.ai/instance/hhs/")
HHS_ONT = Namespace("http://example.org/hhs/ontology#")

# Default input files (see scripts/data_extraction/load_to_db.py)
DEFAULT_INPUT_FILES = (
    "21_lang_debug.ttl",
    "22_cognition_debug.ttl",
    "23_self_care_debug.ttl",
    "24_social_emotions_debug.ttl",
    "25_gross_motor_debug.ttl",
    "26_fine_motor_debug.ttl",
)

# Regex pieces (Unicode dashes)
_DASH = r"[-–—~至到]"
_AGE_RANGE_YEARS = re.compile(
    rf"(?P<lo>\d+)\s*{_DASH}\s*(?P<hi>\d+)\s*岁",
)
_AGE_SINGLE_YEAR = re.compile(r"(?P<n>\d+)\s*岁")
_UNIVERSAL_AGE = re.compile(r"适用年龄\s*[:：]\s*通用")
_MODULE_IN_TEXT = re.compile(
    r"模块\s*[:：]\s*(?P<mod>[^\n／/]+?)(?:\s*$|(?=\s*[／/])|\s*\|)",
)
# Title noise
_PREFIX_LETTER_ENUM = re.compile(r"^\s*[A-Za-z]\.\s*")
_PREFIX_PAREN_NUM = re.compile(r"^\s*\(\d+\)\s*")
_PREFIX_NUM_ENUM = re.compile(r"^\s*\d+[\.)]\s*")
_TRAILING_AGE_RANGE = re.compile(
    rf"\s*[／/]\s*\d+\s*{_DASH}\s*\d+\s*岁\s*$",
)
_TRAILING_AGE_SINGLE = re.compile(r"\s*[／/]\s*\d+\s*岁\s*$")


def _literal_str(node: object) -> str:
    if isinstance(node, Literal):
        return str(node.value) if hasattr(node, "value") else str(node)
    return str(node)


def primary_zh_label(graph: Graph, subject: URIRef) -> str:
    """Prefer zh; otherwise first rdfs:label."""
    zh: Optional[str] = None
    any_label: Optional[str] = None
    for lit in graph.objects(subject, RDFS.label):
        s = _literal_str(lit).strip()
        if not s:
            continue
        if isinstance(lit, Literal) and (lit.language or "").lower().startswith("zh"):
            zh = s
            break
        if any_label is None:
            any_label = s
    return zh or any_label or ""


def collect_literal_texts(graph: Graph, subject: URIRef) -> list[str]:
    """Gather human-readable strings from common annotation properties."""
    texts: list[str] = []
    for pred in (RDFS.label, RDFS.comment):
        for lit in graph.objects(subject, pred):
            s = _literal_str(lit).strip()
            if s and s not in texts:
                texts.append(s)
    return texts


def parse_age_months_from_text(text: str) -> tuple[Optional[int], Optional[int]]:
    """
    Return (min_age_months, max_age_months) or (None, None) if not found.
    - '适用年龄: 通用' -> (0, 72)
    - '3-4 岁' range -> (36, 48)
    - Single '5 岁' -> (60, 60)
    """
    if _UNIVERSAL_AGE.search(text):
        return 0, 72
    m = _AGE_RANGE_YEARS.search(text)
    if m:
        lo = int(m.group("lo"))
        hi = int(m.group("hi"))
        if lo > hi:
            lo, hi = hi, lo
        return lo * 12, hi * 12
    m2 = _AGE_SINGLE_YEAR.search(text)
    if m2:
        n = int(m2.group("n"))
        months = n * 12
        return months, months
    return None, None


def extract_module_from_text(text: str) -> Optional[str]:
    m = _MODULE_IN_TEXT.search(text)
    if not m:
        return None
    mod = m.group("mod").strip()
    return mod or None


def climb_ancestors(graph: Graph, leaf: URIRef) -> tuple[str, str, str, str]:
    """
    Same hierarchy as scripts/ingest_hhs_to_db.climb_ancestors:
    module, submodule, objective, phasal.
    """
    phasal_list: list = []
    for pred in (HHS_ONT.hasGoal, HHS_ONT.hasTask):
        phasal_list.extend(list(graph.subjects(pred, leaf)))
    phasal = phasal_list[0] if phasal_list else None
    if phasal is None:
        return "", "", "", ""

    obj_list = list(graph.subjects(HHS_ONT.hasPhasalObjective, phasal))
    objective = obj_list[0] if obj_list else None

    sub_list = list(graph.subjects(HHS_ONT.hasObjective, objective)) if objective else []
    submodule = sub_list[0] if sub_list else None

    mod_list = list(graph.subjects(HHS_ONT.hasSubmodule, submodule)) if submodule else []
    module = mod_list[0] if mod_list else None

    return (
        primary_zh_label(graph, module) if module else "",
        primary_zh_label(graph, submodule) if submodule else "",
        primary_zh_label(graph, objective) if objective else "",
        primary_zh_label(graph, phasal) if phasal else "",
    )


def extract_module_for_node(graph: Graph, node: URIRef, label: str) -> Optional[str]:
    """Try label first, then ancestor labels (module .. phasal), then any literal on ancestors."""
    for text in [label] + collect_literal_texts(graph, node):
        mod = extract_module_from_text(text)
        if mod:
            return mod
    mod_l, sub_l, obj_l, ph_l = climb_ancestors(graph, node)
    for text in (mod_l, sub_l, obj_l, ph_l):
        mod = extract_module_from_text(text)
        if mod:
            return mod
    return None


def clean_label(raw: str) -> str:
    """Strip enumeration prefixes and trailing age segments."""
    s = raw.strip()
    s = _UNIVERSAL_AGE.sub("", s)
    s = s.strip()
    s = _TRAILING_AGE_RANGE.sub("", s)
    s = _TRAILING_AGE_SINGLE.sub("", s)
    s = _PREFIX_LETTER_ENUM.sub("", s)
    s = _PREFIX_PAREN_NUM.sub("", s)
    s = _PREFIX_NUM_ENUM.sub("", s)
    return s.strip()


def iter_task_nodes(
    graph: Graph,
    task_types: Iterable[URIRef],
) -> list[URIRef]:
    seen: set[str] = set()
    out: list[URIRef] = []
    for t in task_types:
        for subj in graph.subjects(RDF.type, t):
            if not isinstance(subj, URIRef):
                continue
            key = str(subj)
            if key in seen:
                continue
            seen.add(key)
            out.append(subj)
    return out


def enrich_graph(graph: Graph, task_types: tuple[URIRef, ...]) -> None:
    for task in iter_task_nodes(graph, task_types):
        label = primary_zh_label(graph, task)
        min_m: Optional[int]
        max_m: Optional[int]

        min_m, max_m = parse_age_months_from_text(label)
        if min_m is None:
            ag = graph.value(task, HHS_ONT.ageGroup)
            if ag is not None:
                min_m, max_m = parse_age_months_from_text(_literal_str(ag))

        if min_m is not None and max_m is not None:
            graph.set(
                (
                    task,
                    CUMA_SCHEMA.minAgeMonths,
                    Literal(min_m, datatype=XSD.integer),
                )
            )
            graph.set(
                (
                    task,
                    CUMA_SCHEMA.maxAgeMonths,
                    Literal(max_m, datatype=XSD.integer),
                )
            )

        module = extract_module_for_node(graph, task, label)
        if module:
            graph.set((task, CUMA_SCHEMA.module, Literal(module, lang="zh")))

        cleaned = clean_label(label)
        if cleaned:
            graph.set((task, CUMA_SCHEMA.cleanLabel, Literal(cleaned, lang="zh")))


def bind_prefixes(g: Graph) -> None:
    g.bind("cuma-schema", CUMA_SCHEMA)
    g.bind("xsd", XSD)
    g.bind("rdfs", RDFS)
    g.bind("rdf", RDF)
    g.bind("hhs-inst", HHS_INST)
    g.bind("hhs-ont", HHS_ONT)


def parse_task_types(arg: Optional[str]) -> tuple[URIRef, ...]:
    if arg:
        return tuple(URIRef(x.strip()) for x in arg.split(",") if x.strip())
    return (HHS_INST.Task, HHS_ONT.Goal)


def main() -> int:
    base = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Enrich HHS Turtle files with cuma-schema age/module/cleanLabel triples.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=base / "scripts" / "data_extraction",
        help="Directory containing the six *_debug.ttl (or domain) files",
    )
    parser.add_argument(
        "--inputs",
        nargs="*",
        default=list(DEFAULT_INPUT_FILES),
        help="TTL filenames (default: six HHS debug files)",
    )
    parser.add_argument(
        "--task-types",
        type=str,
        default=None,
        help=(
            "Comma-separated full IRIs for rdf:type to enrich "
            '(default: "http://cuma.ai/instance/hhs/Task,http://example.org/hhs/ontology#Goal")'
        ),
    )
    args = parser.parse_args()

    task_types = parse_task_types(args.task_types)
    data_dir: Path = args.data_dir

    if not data_dir.is_dir():
        print(f"❌ data-dir is not a directory: {data_dir}", file=sys.stderr)
        return 1

    written = 0
    for name in args.inputs:
        path = data_dir / name
        if not path.exists():
            print(f"⚠️  Skip missing: {path}", file=sys.stderr)
            continue

        g = Graph()
        g.parse(path, format="turtle")
        enrich_graph(g, task_types)
        bind_prefixes(g)

        out_path = path.with_name(f"{path.stem}_enriched{path.suffix}")
        g.serialize(destination=str(out_path), format="turtle", encoding="utf-8")
        print(f"✅ Wrote {out_path}")
        written += 1

    if written == 0:
        print("No files written. Check --data-dir and filenames.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
