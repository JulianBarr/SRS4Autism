#!/usr/bin/env python3
"""
Batch-generate bilingual parent-facing survey TTL from VB-MAPP Milestone nodes
using Gemini, with checkpointing and level-1 bottleneck tagging.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

import google.generativeai as genai
from dotenv import load_dotenv
from rdflib import Graph
from rdflib.namespace import RDF, RDFS
from rdflib.term import URIRef

# -----------------------------------------------------------------------------
# Paths (project root = two levels up from this file)
# -----------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

SURVEY_SCHEMA_TTL = PROJECT_ROOT / "knowledge_graph" / "ontology" / "survey_schema.ttl"
VBMAPP_CANDIDATES = [
    PROJECT_ROOT / "knowledge_graph" / "ontology" / "vbmapp_woven_ontology.ttl",
    SCRIPT_DIR / "vbmapp_woven_ontology.ttl",
]
OUTPUT_TTL = PROJECT_ROOT / "knowledge_graph" / "survey_parent_full.ttl"

VBMAPP_SCHEMA = "http://cuma.ai/schema/vbmapp/"
VBMAPP_INST = "http://cuma.ai/instance/vbmapp/"

BATCH_SIZE = 5
API_RETRY_SLEEP_SEC = 10
MODEL_NAME = "gemini-2.5-flash"

EVALUATES_NODE_PATTERN = re.compile(
    r"evaluatesNode\s+<([^>]+)>", re.IGNORECASE | re.MULTILINE
)
# Alternate Turtle style: evaluatesNode vbmapp-inst:mand_1_m .
EVALUATES_NODE_CURIE_PATTERN = re.compile(
    r"evaluatesNode\s+vbmapp-inst:([A-Za-z0-9_]+)\s*\.",
    re.IGNORECASE | re.MULTILINE,
)
TURTLE_FENCE_PATTERN = re.compile(
    r"```(?:turtle|ttl)\s*\n(.*?)```", re.IGNORECASE | re.DOTALL
)


def resolve_vbmapp_ttl() -> Path:
    for p in VBMAPP_CANDIDATES:
        if p.is_file():
            return p
    tried = ", ".join(str(p) for p in VBMAPP_CANDIDATES)
    raise FileNotFoundError(
        f"vbmapp_woven_ontology.ttl not found. Tried: {tried}"
    )


def load_checkpoint_evaluates_uris(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8", errors="replace")
    out: set[str] = set(EVALUATES_NODE_PATTERN.findall(text))
    for local in EVALUATES_NODE_CURIE_PATTERN.findall(text):
        out.add(f"{VBMAPP_INST}{local}")
    return out


def extract_local_name(uri: str) -> str:
    if uri.startswith("http://") or uri.startswith("https://"):
        parsed = urlparse(uri)
        seg = parsed.path.rstrip("/").split("/")[-1]
        if seg:
            return seg
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rsplit("/", 1)[-1]


def extract_milestone_index(uri: str, label: Optional[str]) -> Optional[int]:
    """Prefer patterns like mand_5_m -> 5; fallback to first integer in label."""
    local = extract_local_name(uri)
    m = re.search(r"_(\d+)_m(?:\b|_)", local)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)", local)
    if m:
        return int(m.group(1))
    if label:
        m = re.search(r"\b(\d+)\b", label)
        if m:
            return int(m.group(1))
    return None


def iter_milestone_rows(g: Graph) -> list[dict[str, Any]]:
    """Return Milestone nodes with level, label, and bottleneck flag."""
    milestone = URIRef(VBMAPP_SCHEMA + "Milestone")
    level_pred = URIRef(VBMAPP_SCHEMA + "level")
    domain_name = URIRef(VBMAPP_SCHEMA + "domainName")
    description = URIRef(VBMAPP_SCHEMA + "description")
    scoring = URIRef(VBMAPP_SCHEMA + "scoringCriteria")

    rows: list[dict[str, Any]] = []
    for m in g.subjects(RDF.type, milestone):
        uri = str(m)
        label_lit = g.value(m, RDFS.label)
        label = str(label_lit) if label_lit else None
        lvl_lit = g.value(m, level_pred)
        level: Optional[int] = None
        if lvl_lit is not None:
            try:
                level = int(lvl_lit)
            except (TypeError, ValueError):
                level = None

        idx = extract_milestone_index(uri, label)
        is_bottleneck = bool(
            level == 1 and idx is not None and idx in (1, 5)
        )

        dn_lit = g.value(m, domain_name)
        desc_lit = g.value(m, description)
        score_lit = g.value(m, scoring)

        rows.append(
            {
                "uri": uri,
                "label": label or "",
                "level": level,
                "milestone_index": idx,
                "is_bottleneck": is_bottleneck,
                "domainName": str(dn_lit) if dn_lit else "",
                "description": str(desc_lit) if desc_lit else "",
                "scoringCriteria": str(score_lit) if score_lit else "",
            }
        )
    rows.sort(key=lambda r: r["uri"])
    return rows


def build_user_payload(batch: list[dict[str, Any]]) -> str:
    lines: list[str] = [
        "Convert the following VB-MAPP Milestone nodes into parent-facing survey "
        "Turtle (see system instructions). One question per node.\n",
    ]
    for i, row in enumerate(batch, 1):
        lines.append(f"--- Node {i} ---")
        lines.append(f"vb_milestone_uri: {row['uri']}")
        lines.append(f"rdfs_label_en: {row['label']}")
        lines.append(f"vbmapp_level: {row['level']}")
        lines.append(f"extracted_milestone_number: {row['milestone_index']}")
        lines.append(f"is_bottleneck: {str(row['is_bottleneck']).lower()}")
        lines.append(f"domainName: {row['domainName']}")
        lines.append(f"description: {row['description'][:4000]}")
        if row["scoringCriteria"]:
            lines.append(
                f"scoringCriteria_excerpt: {row['scoringCriteria'][:2000]}"
            )
        lines.append("")
    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = """You are a top-tier BCBA (Board Certified Behavior Analyst).

Task: Turn each provided VB-MAPP Milestone into one parent-friendly survey question for progressive assessment.

Output rules (strict):
1) Output ONLY content inside ONE fenced block: use markdown ```turtle ... ``` and put valid Turtle inside the fence. No prose outside the fence.
2) Follow the CUMA survey vocabulary in survey_schema.ttl: classes cuma-survey:ParentQuestion and cuma-survey:Option; properties cuma-survey:evaluatesNode, cuma-survey:promptTemplate, cuma-survey:hasOption, cuma-survey:optionText, cuma-survey:stateAction, and when applicable cuma-survey:isBottleneck.
3) Use prefix cuma-survey: <http://cuma.ai/schema/survey/> and declare @prefix rdfs: and @prefix xsd: as needed. Use a distinct instance URI per question under a stable path such as <http://cuma.ai/instance/survey/parent#...> or <http://cuma.ai/instance/survey/...> — your choice, but be consistent and unique per question.
4) cuma-survey:evaluatesNode MUST reference the exact VB milestone URI given in the input (full IRI in angle brackets).
5) cuma-survey:promptTemplate MUST include BOTH language tags: one @en and one @zh string for the same template. Each MUST contain the placeholders {{child_name}} and {{pronoun}}.
6) Exactly three options per question, in this order, with these stateAction values:
   - Cannot do it / 无法完成 -> cuma-survey:stateAction "FAIL" .
   - Needs prompts / 需提示 -> cuma-survey:stateAction "FAIL_PROMPT_DEPENDENT" .
   - Does it independently / 独立完成 -> cuma-survey:stateAction "PASS_NODE" .
7) If the input line is_bottleneck is true, add: cuma-survey:isBottleneck "true"^^xsd:boolean . on that ParentQuestion. If false, omit isBottleneck.
8) ParentQuestion typing: each question instance a cuma-survey:ParentQuestion .

--- survey_schema.ttl (authoritative vocabulary) ---
<<<SCHEMA_TTL_INLINE>>>
"""


def extract_turtle_from_response(text: str) -> str:
    matches = TURTLE_FENCE_PATTERN.findall(text)
    if matches:
        return "\n\n".join(m.strip() for m in matches).strip()
    return text.strip()


def chunked(items: list[Any], n: int) -> Iterable[list[Any]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


def append_ttl_block(path: Path, block: str, is_first: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix_header = """@prefix cuma-survey: <http://cuma.ai/schema/survey/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

"""
    mode = "w" if is_first else "a"
    with open(path, mode, encoding="utf-8") as f:
        if is_first:
            f.write(prefix_header)
        f.write(block.rstrip() + "\n")


def main() -> None:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Set GEMINI_API_KEY (e.g. in .env).")
        raise SystemExit(1)

    if not SURVEY_SCHEMA_TTL.is_file():
        print(f"Missing survey schema: {SURVEY_SCHEMA_TTL}")
        raise SystemExit(1)

    vbmapp_path = resolve_vbmapp_ttl()

    g = Graph()
    g.parse(SURVEY_SCHEMA_TTL.as_posix(), format="turtle")
    g.parse(vbmapp_path.as_posix(), format="turtle")

    done_uris = load_checkpoint_evaluates_uris(OUTPUT_TTL)
    rows = iter_milestone_rows(g)
    pending = [r for r in rows if r["uri"] not in done_uris]

    total = len(rows)
    remaining = len(pending)
    print(
        f"Milestones total={total}, already in output={len(done_uris)}, "
        f"to process={remaining}"
    )

    if not pending:
        print("Nothing to do; all milestones already have survey entries.")
        return

    schema_ttl_text = SURVEY_SCHEMA_TTL.read_text(encoding="utf-8")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.replace(
        "<<<SCHEMA_TTL_INLINE>>>", schema_ttl_text
    )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=system_prompt)

    file_exists = OUTPUT_TTL.is_file() and OUTPUT_TTL.stat().st_size > 0
    # First write only if file missing or empty; if checkpoint had matches but file empty, still first write.
    first_write = not file_exists

    processed_in_run = 0
    batch_num = 0
    for batch in chunked(pending, BATCH_SIZE):
        batch_num += 1
        user_text = build_user_payload(batch)
        response_text = ""
        while True:
            try:
                resp = model.generate_content(user_text)
                response_text = (resp.text or "").strip()
                break
            except Exception as exc:  # noqa: BLE001 — retry all API errors
                print(
                    f"API error (batch {batch_num}): {exc!s}; "
                    f"retrying in {API_RETRY_SLEEP_SEC}s..."
                )
                time.sleep(API_RETRY_SLEEP_SEC)

        turtle_body = extract_turtle_from_response(response_text)
        if not turtle_body:
            print(f"Warning: empty turtle for batch {batch_num}; raw response saved to stderr length check.")
            raise RuntimeError(f"Empty turtle extraction for batch {batch_num}")

        append_ttl_block(OUTPUT_TTL, turtle_body, is_first=first_write)
        first_write = False
        processed_in_run += len(batch)

        for r in batch:
            done_uris.add(r["uri"])

        print(
            f"Batch {batch_num}: wrote {len(batch)} question(s); "
            f"cumulative done={len(done_uris)}/{total} "
            f"(+{processed_in_run} this run)"
        )

    print(f"Finished. Output: {OUTPUT_TTL}")


if __name__ == "__main__":
    main()
