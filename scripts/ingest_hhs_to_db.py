#!/usr/bin/env python3
"""
Ingest Heep Hong Society (HHS) curriculum goals from Turtle files into SQLite (hhs_goals).

Reads the six domain files under scripts/data_extraction/:
  21_language.ttl, 22_cognition.ttl, 23_self_care.ttl,
  24_social_emotions.ttl, 25_gross_motor.ttl, 26_fine_motor.ttl

Upserts by goal_iri (and stable quest_id). Run from project root with venv activated:
  python scripts/ingest_hhs_to_db.py

Optional: seed FSRS "New" card entries on every profile (--seed-fsrs-new).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import opencc

# Project root
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from rdflib import Graph, Literal, Namespace, RDF, URIRef  # noqa: E402
from rdflib.namespace import RDFS  # noqa: E402

HHS_ONT = Namespace("http://example.org/hhs/ontology#")
T2S_CONVERTER = opencc.OpenCC("t2s.json")
NOISY_PREFIXES = (
    "/ 建议教材：",
    "建议教材：",
    "活动: * **Activities:**",
    "活动：",
)
MATERIAL_VERB_HINTS = ("示范", "把", "放在", "接着", "然后", "引导", "让儿童")

DOMAIN_FILES = (
    "21_language.ttl",
    "22_cognition.ttl",
    "23_self_care.ttl",
    "24_social_emotions.ttl",
    "25_gross_motor.ttl",
    "26_fine_motor.ttl",
)


def get_db_path() -> Path:
    for subdir in ("content_db", ""):
        base = BASE_DIR / "data" / subdir if subdir else BASE_DIR / "data"
        p = base / "srs4autism.db"
        if p.exists():
            return p
    return BASE_DIR / "data" / "content_db" / "srs4autism.db"


def stable_quest_id(goal_iri: str) -> str:
    h = hashlib.sha256(goal_iri.encode("utf-8")).hexdigest()[:16]
    return f"hhs_{h}"


def literal_to_str(node: Any) -> str:
    if isinstance(node, Literal):
        return str(node.value) if hasattr(node, "value") else str(node)
    return str(node)


def rdfs_label(g: Graph, uri: URIRef) -> str:
    for lit in g.objects(uri, RDFS.label):
        return literal_to_str(lit).strip()
    return ""


def collect_literals(g: Graph, subj: URIRef, pred) -> list[str]:
    out: list[str] = []
    for o in g.objects(subj, pred):
        s = literal_to_str(o).strip()
        if s and s not in out:
            out.append(s)
    return out


def _convert_and_clean_text(text: str) -> str:
    normalized = T2S_CONVERTER.convert(str(text or "")).strip()
    for prefix in NOISY_PREFIXES:
        prefix_pattern = r"^\s*" + re.escape(prefix) + r"\s*"
        normalized = re.sub(prefix_pattern, "", normalized).strip()
    return normalized


def cleanse_string_list(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        normalized = _convert_and_clean_text(item)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def should_move_material_to_activity(material: str) -> bool:
    if len(material) > 18:
        return True
    return any(verb in material for verb in MATERIAL_VERB_HINTS)


def cleanse_goal_row(row: dict[str, Any]) -> dict[str, Any]:
    row["label"] = _convert_and_clean_text(row.get("label", ""))
    row["module_label"] = _convert_and_clean_text(row.get("module_label", ""))

    for field in (
        "submodule_label",
        "objective_label",
        "phasal_label",
        "goal_code",
        "age_group",
        "passing_criteria",
    ):
        value = row.get(field)
        if isinstance(value, str):
            row[field] = _convert_and_clean_text(value)

    breadcrumb = json.loads(row.get("breadcrumb_json") or "[]")
    if isinstance(breadcrumb, list):
        row["breadcrumb_json"] = json.dumps(
            cleanse_string_list([str(item) for item in breadcrumb]),
            ensure_ascii=False,
        )

    materials = cleanse_string_list(json.loads(row.get("materials_json") or "[]"))
    activities = cleanse_string_list(json.loads(row.get("activities_json") or "[]"))
    precautions = cleanse_string_list(json.loads(row.get("precautions_json") or "[]"))

    kept_materials: list[str] = []
    for material in materials:
        if should_move_material_to_activity(material):
            if material not in activities:
                activities.append(material)
        else:
            kept_materials.append(material)

    row["materials_json"] = json.dumps(kept_materials, ensure_ascii=False)
    row["activities_json"] = json.dumps(activities, ensure_ascii=False)
    row["precautions_json"] = json.dumps(precautions, ensure_ascii=False)
    return row


def climb_ancestors(g: Graph, goal: URIRef) -> tuple[str, str, str, str]:
    """
    Return (module_label, submodule_label, objective_label, phasal_label).
    Missing levels use empty string.
    """
    phasal_list = list(g.subjects(HHS_ONT.hasGoal, goal))
    phasal = phasal_list[0] if phasal_list else None
    if phasal is None:
        return "", "", "", ""

    obj_list = list(g.subjects(HHS_ONT.hasPhasalObjective, phasal))
    objective = obj_list[0] if obj_list else None

    sub_list = list(g.subjects(HHS_ONT.hasObjective, objective)) if objective else []
    submodule = sub_list[0] if sub_list else None

    mod_list = list(g.subjects(HHS_ONT.hasSubmodule, submodule)) if submodule else []
    module = mod_list[0] if mod_list else None

    return (
        rdfs_label(g, module) if module else "",
        rdfs_label(g, submodule) if submodule else "",
        rdfs_label(g, objective) if objective else "",
        rdfs_label(g, phasal) if phasal else "",
    )


def parse_goals_from_file(path: Path) -> list[dict[str, Any]]:
    g = Graph()
    g.parse(str(path), format="turtle")
    rows: list[dict[str, Any]] = []

    for goal in g.subjects(RDF.type, HHS_ONT.Goal):
        if not isinstance(goal, URIRef):
            continue
        goal_iri = str(goal)
        label = rdfs_label(g, goal)
        mod, subm, obj, phasal = climb_ancestors(g, goal)
        breadcrumb = [x for x in (mod, subm, obj, phasal) if x]

        goal_code: Optional[str] = None
        for o in g.objects(goal, HHS_ONT.goalCode):
            goal_code = literal_to_str(o).strip()
            break

        age_group: Optional[str] = None
        for o in g.objects(goal, HHS_ONT.ageGroup):
            age_group = literal_to_str(o).strip()
            break

        materials = collect_literals(g, goal, HHS_ONT.hasMaterial)
        activities = collect_literals(g, goal, HHS_ONT.hasActivity)
        precautions = collect_literals(g, goal, HHS_ONT.hasPrecaution)

        passing: Optional[str] = None
        for o in g.objects(goal, HHS_ONT.hasPassingCriteria):
            passing = literal_to_str(o).strip()
            break

        rows.append(
            cleanse_goal_row(
                {
                    "quest_id": stable_quest_id(goal_iri),
                    "goal_iri": goal_iri,
                    "content_source": "HHS",
                    "domain_file": path.name,
                    "label": label or "(未命名)",
                    "module_label": mod or "未知模块",
                    "submodule_label": subm or None,
                    "objective_label": obj or None,
                    "phasal_label": phasal or None,
                    "breadcrumb_json": json.dumps(breadcrumb, ensure_ascii=False),
                    "goal_code": goal_code,
                    "age_group": age_group,
                    "materials_json": json.dumps(materials, ensure_ascii=False),
                    "activities_json": json.dumps(activities, ensure_ascii=False),
                    "precautions_json": json.dumps(precautions, ensure_ascii=False),
                    "passing_criteria": passing,
                }
            )
        )
    return rows


def upsert_rows(db_path: Path, rows: list[dict[str, Any]]) -> tuple[int, int]:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    inserted = 0
    updated = 0
    for r in rows:
        cur.execute("SELECT id FROM hhs_goals WHERE goal_iri = ?", (r["goal_iri"],))
        exists = cur.fetchone()
        if exists:
            updated += 1
            cur.execute(
                """
                UPDATE hhs_goals SET
                    quest_id = ?, content_source = ?, domain_file = ?, label = ?,
                    module_label = ?, submodule_label = ?, objective_label = ?, phasal_label = ?,
                    breadcrumb_json = ?, goal_code = ?, age_group = ?,
                    materials_json = ?, activities_json = ?, precautions_json = ?,
                    passing_criteria = ?, updated_at = CURRENT_TIMESTAMP
                WHERE goal_iri = ?
                """,
                (
                    r["quest_id"],
                    r["content_source"],
                    r["domain_file"],
                    r["label"],
                    r["module_label"],
                    r["submodule_label"],
                    r["objective_label"],
                    r["phasal_label"],
                    r["breadcrumb_json"],
                    r["goal_code"],
                    r["age_group"],
                    r["materials_json"],
                    r["activities_json"],
                    r["precautions_json"],
                    r["passing_criteria"],
                    r["goal_iri"],
                ),
            )
        else:
            inserted += 1
            cur.execute(
                """
                INSERT INTO hhs_goals (
                    quest_id, goal_iri, content_source, domain_file, label,
                    module_label, submodule_label, objective_label, phasal_label,
                    breadcrumb_json, goal_code, age_group,
                    materials_json, activities_json, precautions_json, passing_criteria,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    r["quest_id"],
                    r["goal_iri"],
                    r["content_source"],
                    r["domain_file"],
                    r["label"],
                    r["module_label"],
                    r["submodule_label"],
                    r["objective_label"],
                    r["phasal_label"],
                    r["breadcrumb_json"],
                    r["goal_code"],
                    r["age_group"],
                    r["materials_json"],
                    r["activities_json"],
                    r["precautions_json"],
                    r["passing_criteria"],
                ),
            )
    conn.commit()
    conn.close()
    return inserted, updated


def ensure_table(db_path: Path) -> None:
    sql_path = BASE_DIR / "backend" / "migrations" / "add_hhs_goals_table.sql"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='hhs_goals'"
    )
    if cur.fetchone():
        conn.close()
        return
    if sql_path.exists():
        conn.executescript(sql_path.read_text(encoding="utf-8"))
        conn.commit()
    else:
        conn.close()
        raise RuntimeError(
            f"hhs_goals table missing and {sql_path} not found. "
            "Run backend init_db or apply add_hhs_goals_table.sql"
        )
    conn.close()


def seed_fsrs_new_for_all_profiles(db_path: Path, quest_ids: list[str]) -> int:
    """Insert FSRS Card.to_dict() for missing quest_ids (state New) on every profile."""
    try:
        from fsrs import Card
    except ImportError:
        print("fsrs not installed; skip --seed-fsrs-new", file=sys.stderr)
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, extracted_data FROM profiles")
    rows = cur.fetchall()
    touched = 0
    new_card = Card().to_dict()
    for row in rows:
        raw = row["extracted_data"]
        data = json.loads(raw) if raw else {}
        fsrs = data.setdefault("fsrs_states", {})
        changed = False
        for qid in quest_ids:
            if qid not in fsrs:
                fsrs[qid] = dict(new_card)
                changed = True
        if changed:
            touched += 1
            cur.execute(
                "UPDATE profiles SET extracted_data = ?, updated_at = ? WHERE id = ?",
                (
                    json.dumps(data, ensure_ascii=False),
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    row["id"],
                ),
            )
    conn.commit()
    conn.close()
    return touched


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest HHS TTL goals into hhs_goals table")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=BASE_DIR / "scripts" / "data_extraction",
        help="Directory containing 21_language.ttl … 26_fine_motor.ttl",
    )
    parser.add_argument("--db", type=Path, default=None, help="SQLite path (default: data/content_db/srs4autism.db)")
    parser.add_argument(
        "--seed-fsrs-new",
        action="store_true",
        help="Add default FSRS card state for every HHS quest_id on all profiles (state New)",
    )
    args = parser.parse_args()

    db_path = args.db or get_db_path()
    if not db_path.parent.is_dir():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    ensure_table(db_path)

    all_rows: list[dict[str, Any]] = []
    for name in DOMAIN_FILES:
        path = args.data_dir / name
        if not path.exists():
            print(f"⚠️  Skip missing file: {path}", file=sys.stderr)
            continue
        part = parse_goals_from_file(path)
        print(f"📄 {name}: {len(part)} goals")
        all_rows.extend(part)

    if not all_rows:
        print("No goals parsed. Check --data-dir and TTL files.", file=sys.stderr)
        sys.exit(1)

    ins, upd = upsert_rows(db_path, all_rows)
    print(f"✅ Upsert complete: inserted={ins}, updated={upd}, total rows={len(all_rows)}")

    if args.seed_fsrs_new:
        ids = list({r["quest_id"] for r in all_rows})
        n = seed_fsrs_new_for_all_profiles(db_path, ids)
        print(f"✅ Seeded fsrs_states for HHS quest_ids on {n} profile(s)")


if __name__ == "__main__":
    main()
