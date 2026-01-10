"""
Knowledge Graph Client for abstracting SPARQL query execution.

This module provides a unified interface for querying the knowledge graph,
supporting both Fuseki and Oxigraph backends.
"""

import requests
from typing import Dict, Any, Optional
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
    Client for executing SPARQL queries against a knowledge graph endpoint.

    Supports both Fuseki and Oxigraph backends by abstracting the HTTP layer.

    Example:
        >>> client = KnowledgeGraphClient()
        >>> query = "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
        >>> results = client.query(query)
        >>> bindings = results.get("results", {}).get("bindings", [])
    """

    def __init__(self, endpoint_url: Optional[str] = None, timeout: int = 30):
        """
        Initialize the knowledge graph client.

        Args:
            endpoint_url: SPARQL endpoint URL. If None, uses settings.fuseki_url
            timeout: Request timeout in seconds (default: 30)
        """
        self.endpoint_url = endpoint_url or settings.fuseki_url
        self.timeout = timeout

    def query(self, sparql_query: str) -> Dict[str, Any]:
        """
        Execute a SPARQL query and return the results.

        Args:
            sparql_query: SPARQL query string

        Returns:
            Dictionary containing query results in SPARQL JSON format

        Raises:
            KnowledgeGraphConnectionError: If connection to endpoint fails
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
            # Bypass proxy for localhost/127.0.0.1 to avoid Privoxy issues
            proxies = {
                'http': None,
                'https': None,
            } if 'localhost' in self.endpoint_url or '127.0.0.1' in self.endpoint_url else None

            response = requests.post(
                self.endpoint_url,
                data={"query": sparql_query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=self.timeout,
                proxies=proxies,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout as e:
            raise KnowledgeGraphConnectionError(
                f"Timeout connecting to knowledge graph at {self.endpoint_url}"
            ) from e

        except requests.exceptions.ConnectionError as e:
            raise KnowledgeGraphConnectionError(
                f"Failed to connect to knowledge graph at {self.endpoint_url}"
            ) from e

        except requests.exceptions.HTTPError as e:
            raise KnowledgeGraphQueryError(
                f"Query execution failed with status {response.status_code}: {response.text}"
            ) from e

        except requests.exceptions.RequestException as e:
            raise KnowledgeGraphError(
                f"Unexpected error querying knowledge graph: {str(e)}"
            ) from e

        except ValueError as e:
            raise KnowledgeGraphQueryError(
                f"Failed to parse JSON response from knowledge graph"
            ) from e

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
        Check if the knowledge graph endpoint is accessible.

        Returns:
            True if endpoint is accessible, False otherwise
        """
        try:
            # Simple ASK query to test connectivity
            query = "ASK { ?s ?p ?o }"
            self.query(query)
            return True
        except KnowledgeGraphError:
            return False
