#!/usr/bin/env python3
"""Decode percent-encoded hhh-inst: local names, convert Traditional→Simplified, write *_abox_cleaned.ttl."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

from opencc import OpenCC

# Matches prefixed IRIs like hhh-inst:%E8%A8%80 (encoded local segment)
HHH_INST_ENCODED = re.compile(r"hhh-inst:%[A-Za-z0-9%_-]+")

# Characters the user asked to normalize for safe-ish URI local parts
_INVALID_LOCAL_CHARS = re.compile(r"[\s\[\]()\\/]+")


def _sanitize_local_part(decoded: str) -> str:
    """Replace spaces, brackets, and slashes with single underscores."""
    s = _INVALID_LOCAL_CHARS.sub("_", decoded)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def build_replacement_map(text: str, converter: OpenCC) -> dict[str, str]:
    """Map each encoded hhh-inst token to its decoded + simplified + sanitized form."""
    mapping: dict[str, str] = {}
    for raw in set(HHH_INST_ENCODED.findall(text)):
        encoded_tail = raw[len("hhh-inst:") :]
        decoded = unquote(encoded_tail)
        simplified = converter.convert(decoded)
        local = _sanitize_local_part(simplified)
        new_token = f"hhh-inst:{local}"
        if raw != new_token:
            mapping[raw] = new_token
    return mapping


def transform_ttl(text: str, converter: OpenCC) -> str:
    repl = build_replacement_map(text, converter)
    if not repl:
        return text
    out = text
    for old in sorted(repl, key=len, reverse=True):
        out = out.replace(old, repl[old])
    return out


def iter_abox_sources(directory: Path) -> list[Path]:
    """All *_abox.ttl files excluding already-cleaned outputs."""
    paths: list[Path] = []
    for p in sorted(directory.glob("*_abox.ttl")):
        if p.name.endswith("_abox_cleaned.ttl"):
            continue
        paths.append(p)
    return paths


def cleaned_output_path(source: Path) -> Path:
    return source.with_name(f"{source.stem}_cleaned{source.suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decode hhh-inst percent-encoding, t2s OpenCC, emit *_abox_cleaned.ttl."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=str(Path(__file__).resolve().parent),
        help="Directory to scan for *_abox.ttl (default: this script's directory)",
    )
    args = parser.parse_args()
    base = Path(args.directory).resolve()
    if not base.is_dir():
        print(f"Not a directory: {base}", file=sys.stderr)
        return 1

    converter = OpenCC("t2s")
    sources = iter_abox_sources(base)
    if not sources:
        print(f"No *_abox.ttl files under {base}", file=sys.stderr)
        return 0

    for src in sources:
        text = src.read_text(encoding="utf-8")
        out_text = transform_ttl(text, converter)
        dest = cleaned_output_path(src)
        dest.write_text(out_text, encoding="utf-8")
        print(f"Wrote {dest} ({len(out_text)} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
