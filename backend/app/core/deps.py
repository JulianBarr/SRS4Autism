"""Shared FastAPI dependencies (kept small to avoid import cycles)."""

from fastapi import Query

from app.core.types import OntologySource


def get_ontology_source(source: OntologySource = Query("QCQ")) -> OntologySource:
    return source
