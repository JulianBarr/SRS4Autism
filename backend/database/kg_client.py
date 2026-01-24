"""
Knowledge Graph Client for abstracting SPARQL query execution.

This module provides a unified interface for querying the knowledge graph,
using an embedded Oxigraph store.
"""

import requests
import pyoxigraph as oxigraph
import re
from typing import Dict, Any, Optional
from pathlib import Path
from backend.config import settings


def normalize_for_kg(raw_str: str) -> str:
    """
    Normalizes a string for use as a Knowledge Graph identifier.
    Replaces illegal characters ()[]{}\s,<,>,? with an underscore _.
    Matches the logic in in Prompt 2.
    """
    return re.sub(r'[(){}\[\]<>,?\s]', '_', raw_str)


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

    def __init__(self, endpoint_url: Optional[str] = None, timeout: int = 30):
        """
        Initialize the knowledge graph client. Can connect to a Fuseki endpoint or use an embedded Oxigraph store.

        Args:
            endpoint_url: Optional. The URL of the SPARQL endpoint (e.g., Fuseki).
                          If None, an embedded Oxigraph store is used.
            timeout: Request timeout in seconds for Fuseki connections (deprecated for embedded store).
        """
        self.timeout = timeout
        self.endpoint_url = endpoint_url
        self.store = None # For Oxigraph
        self.is_fuseki = False

        if self.endpoint_url and self.endpoint_url != "oxigraph://embedded":
            # Assume Fuseki or compatible external endpoint
            print(f"Connecting to external SPARQL endpoint: {self.endpoint_url}")
            self.is_fuseki = True
        else:
            # Use embedded Oxigraph store
            print("Using embedded Oxigraph store.")
            try:
                from backend.app.utils.oxigraph_utils import get_kg_store
                self.store = get_kg_store()
                self.endpoint_url = "oxigraph://embedded" # Standardize internal representation
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
        if self.is_fuseki:
            raise KnowledgeGraphError("File loading is not supported for external Fuseki endpoints via this client.")
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
        if self.is_fuseki:
            try:
                headers = {"Content-Type": "application/sparql-query"}
                response = requests.post(self.endpoint_url, data=sparql_query.encode('utf-8'), headers=headers, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                raise KnowledgeGraphQueryError(f"Fuseki query failed: {e}") from e
        else:
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
                        try:
                            value = solution[var_name]
                            if value is not None:
                                binding[var_name] = self._convert_term_to_json(value)
                        except (KeyError, TypeError):
                            # Variable not bound in this solution, skip it
                            continue
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
        if self.is_fuseki:
            try:
                response = requests.get(self.endpoint_url, timeout=self.timeout)
                response.raise_for_status()
                return True
            except requests.exceptions.RequestException:
                return False
        else:
            try:
                # Simple ASK query to test connectivity for Oxigraph
                query = "ASK { ?s ?p ?o }"
                self.query(query)
                return True
            except KnowledgeGraphError:
                return False
