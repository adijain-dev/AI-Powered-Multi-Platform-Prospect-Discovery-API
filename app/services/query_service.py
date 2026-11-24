import logging
from typing import Dict, Optional
from app.schemas import QueryUnderstanding
from app.services.llm_service import llm_service
from app.platforms import get_all_platforms

logger = logging.getLogger("prospect_discovery.query")


class QueryService:
    """Service to handle natural language query understanding and search query generation."""

    def __init__(self):
        # In-memory LRU-style cache for parsed queries
        self._query_cache: Dict[str, QueryUnderstanding] = {}

    async def understand_query(self, query: str) -> QueryUnderstanding:
        """
        Understand the search query, extracting audience, interest, and geographical location.
        Uses in-memory cache to save token costs and minimize latency for repeat requests.
        """
        cache_key = query.strip().lower()
        if cache_key in self._query_cache:
            logger.info("Serving query understanding from cache for: '%s'", query)
            return self._query_cache[cache_key]

        understanding = await llm_service.parse_query(query)

        # Store in cache
        if len(self._query_cache) > 1000:
            # Simple eviction of oldest item
            self._query_cache.pop(next(iter(self._query_cache)))
        self._query_cache[cache_key] = understanding

        return understanding

    def generate_platform_queries(self, understanding: QueryUnderstanding) -> Dict[str, str]:
        """
        Generate platform-specific search dorks and queries for all registered discovery platforms.
        """
        queries: Dict[str, str] = {}
        for platform in get_all_platforms():
            queries[platform.name] = platform.generate_search_query(understanding)
        return queries


query_service = QueryService()
