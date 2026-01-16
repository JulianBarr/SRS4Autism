"""
Knowledge Graph Client for abstracting SPARQL query execution.

This module provides a unified interface for querying the knowledge graph,
using an embedded Oxigraph store.
"""

import pyoxigraph as oxigraph
from typing import Dict, Any, Optional
from pathlib import Path
from backend.config import settings
class KnowledgeGraphError(Exception):
    """Base exception for knowledge graph operations."""
    pass


class KnowledgeGraphConnectionError(KnowledgeGraphError):
    """Exception raised when connection to knowledge graph fails."""
    pass


class KnowledgeGraphQueryError(KnowledgeGraphError):
    """Exception raised when SPARQL query execution fails."""
    pass


class KnowledgeGraphClient:
    """
    Client for executing SPARQL queries against an embedded Oxigraph store.

    Example:
        >>> client = KnowledgeGraphClient()
        >>> query = "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
        >>> results = client.query(query)
        >>> bindings = results.get("results", {}).get("bindings", [])
    """

    def __init__(self, store_path: Optional[str] = None, timeout: int = 30):
        """
        Initialize the knowledge graph client with an embedded Oxigraph store.

        Uses the singleton store instance from oxigraph_utils.

        Args:
            store_path: Path to the Oxigraph store directory. If None, uses settings.kg_store_path
            timeout: Deprecated parameter kept for backward compatibility (no longer used with embedded store)
        """
        self.store_path = store_path or settings.kg_store_path
        self.timeout = timeout
        self.endpoint_url = f"oxigraph://{self.store_path}"

        try:
            from backend.app.utils.oxigraph_utils import get_oxigraph_store
            self.store = get_oxigraph_store(self.store_path)
        except Exception as e:
            raise KnowledgeGraphConnectionError(
                f"Failed to connect to Oxigraph store: {str(e)}"
            ) from e

    def load_file(self, file_path: str, format=None) -> None:
        """
        Load RDF data from a file into the store.

        Args:
            file_path: Path to the RDF file to load
            format: RdfFormat for the file. If None, format is guessed from file extension.
                   Common formats: RdfFormat.TURTLE, RdfFormat.RDF_XML, RdfFormat.N_TRIPLES

        Raises:
            KnowledgeGraphError: If loading fails

        Example:
            >>> client = KnowledgeGraphClient()
            >>> client.load_file("knowledge_graph/world_model.ttl")
        """
        try:
            # Use path parameter - pyoxigraph can handle the file directly
            self.store.load(path=file_path, format=format)
        except FileNotFoundError as e:
            raise KnowledgeGraphError(
                f"File not found: {file_path}"
            ) from e
        except Exception as e:
            raise KnowledgeGraphError(
                f"Failed to load file {file_path}: {str(e)}"
            ) from e

    def query(self, sparql_query: str) -> Dict[str, Any]:
        """
        Execute a SPARQL query and return the results in SPARQL JSON format.

        This method converts Oxigraph's native results into the same JSON format
        that Fuseki returns, ensuring frontend compatibility.

        Args:
            sparql_query: SPARQL query string

        Returns:
            Dictionary containing query results in SPARQL JSON format

        Raises:
            KnowledgeGraphQueryError: If query execution fails

        Example:
            >>> client = KnowledgeGraphClient()
            >>> query = '''
            ... PREFIX srs-kg: <http://srs4autism.com/schema/>
            ... SELECT ?word ?label WHERE {
            ...     ?word a srs-kg:Word ;
            ...           rdfs:label ?label .
            ... } LIMIT 10
            ... '''
            >>> results = client.query(query)
        """
        try:
            results = self.store.query(sparql_query)

            # Handle ASK queries - pyoxigraph returns a QueryBoolean object
            if hasattr(results, '__bool__'):
                return {"boolean": bool(results)}

            # Handle SELECT queries
            # Oxigraph returns a QuerySolutions object for SELECT queries
            # Get variable names from the QuerySolutions object
            variables = [var.value for var in results.variables]
            bindings_list = []

            for solution in results:
                binding = {}
                for var_name in variables:
                    value = solution[var_name]
                    if value is not None:
                        binding[var_name] = self._convert_term_to_json(value)

                bindings_list.append(binding)

            return {
                "head": {"vars": variables},
                "results": {"bindings": bindings_list}
            }

        except Exception as e:
            raise KnowledgeGraphQueryError(
                f"Query execution failed: {str(e)}"
            ) from e

    def _convert_term_to_json(self, term) -> Dict[str, str]:
        """
        Convert an Oxigraph term to SPARQL JSON format.

        Args:
            term: Oxigraph term (NamedNode, Literal, or BlankNode)

        Returns:
            Dictionary with 'type' and 'value' keys, matching SPARQL JSON format
        """
        if isinstance(term, oxigraph.NamedNode):
            return {"type": "uri", "value": str(term.value)}
        elif isinstance(term, oxigraph.Literal):
            result = {"type": "literal", "value": str(term.value)}
            if term.language:
                result["xml:lang"] = term.language
            elif term.datatype and str(term.datatype.value) != "http://www.w3.org/2001/XMLSchema#string":
                result["datatype"] = str(term.datatype.value)
            return result
        elif isinstance(term, oxigraph.BlankNode):
            return {"type": "bnode", "value": str(term.value)}
        else:
            return {"type": "literal", "value": str(term)}

    def query_bindings(self, sparql_query: str) -> list[Dict[str, Any]]:
        """
        Execute a SPARQL query and return just the bindings.

        Args:
            sparql_query: SPARQL query string

        Returns:
            List of binding dictionaries

        Example:
            >>> client = KnowledgeGraphClient()
            >>> query = "SELECT ?word WHERE { ?word a srs-kg:Word } LIMIT 5"
            >>> bindings = client.query_bindings(query)
            >>> for row in bindings:
            ...     print(row["word"]["value"])
        """
        results = self.query(sparql_query)
        return results.get("results", {}).get("bindings", [])

    def health_check(self) -> bool:
        """
        Check if the knowledge graph store is accessible.

        Returns:
            True if store is accessible, False otherwise
        """
        try:
            # Simple ASK query to test connectivity
            query = "ASK { ?s ?p ?o }"
            self.query(query)
            return True
        except KnowledgeGraphError:
            return False
