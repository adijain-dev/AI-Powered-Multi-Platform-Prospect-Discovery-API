import asyncio
import logging
import time
from typing import List, Dict, Optional
from app.config import settings
from app.schemas import ProspectRequest, ProspectResponse, Prospect, RawProfileResult
from app.services.query_service import query_service
from app.services.search_service import search_service
from app.services.profile_extractor import profile_extractor
from app.services.relevance_service import relevance_service
from app.services.deduplication_service import deduplication_service
from app.platforms import get_all_platforms

logger = logging.getLogger("prospect_discovery.prospect")


class ProspectService:
    """Master orchestration service for discovering, validating, and consolidating prospects."""

    def __init__(self):
        # Cache for full query responses
        self._response_cache: Dict[str, ProspectResponse] = {}

    async def discover_prospects(self, request: ProspectRequest) -> ProspectResponse:
        """
        Execute full end-to-end prospect discovery pipeline.
        1. Query Understanding (LLM/Heuristic)
        2. Multi-platform Parallel Search
        3. Profile & Contact Extraction
        4. Relevance Scoring & Filtering
        5. Duplicate Detection & Profile Consolidation
        6. Structured Response Generation
        """
        query = request.query.strip()
        cache_key = query.lower()

        # Check response cache
        if settings.ENABLE_CACHE and cache_key in self._response_cache:
            logger.info("Serving prospect discovery response from cache for query: '%s'", query)
            return self._response_cache[cache_key]

        start_time = time.time()
        logger.info("Starting prospect discovery for: '%s'", query)

        # 1. Natural Language Query Understanding
        understanding = await query_service.understand_query(query)
        logger.info(
            "Query Understanding: Audience='%s', Interest='%s', Location='%s', Type='%s'",
            understanding.audience, understanding.interest,
            understanding.location.to_location_string(), understanding.target_type
        )

        # 2. Generate platform-specific search queries
        platform_queries = query_service.generate_platform_queries(understanding)

        # 3. Execute parallel search discovery across supported platforms
        raw_profiles: List[RawProfileResult] = []
        search_tasks = []

        for platform_name, search_query in platform_queries.items():
            search_tasks.append(
                self._search_platform(platform_name, search_query, understanding)
            )

        # Run all platform searches concurrently with failure isolation
        results_nested = await asyncio.gather(*search_tasks, return_exceptions=True)

        for result_batch in results_nested:
            if isinstance(result_batch, list):
                raw_profiles.extend(result_batch)
            elif isinstance(result_batch, Exception):
                logger.warning("Platform search task encountered error: %s", result_batch)

        logger.info("Discovered %d raw profiles across all platforms", len(raw_profiles))

        # 4. Relevance Evaluation & Filtering
        relevant_profiles = relevance_service.filter_and_score(
            profiles=raw_profiles,
            understanding=understanding,
            min_threshold=0.30
        )
        logger.info("Retained %d relevant profiles after scoring & filtering", len(relevant_profiles))

        # 5. Social Profile Consolidation & Duplicate Detection
        consolidated_prospects = deduplication_service.consolidate_prospects(relevant_profiles)

        # Truncate to maximum prospects limit
        final_prospects = consolidated_prospects[: settings.MAX_PROSPECTS_PER_QUERY]

        elapsed = time.time() - start_time
        logger.info(
            "Completed prospect discovery in %.2fs. Total consolidated prospects: %d",
            elapsed, len(final_prospects)
        )

        response = ProspectResponse(
            success=True,
            query=query,
            total_prospects=len(final_prospects),
            prospects=final_prospects
        )

        # Cache response
        if settings.ENABLE_CACHE:
            if len(self._response_cache) > 200:
                self._response_cache.pop(next(iter(self._response_cache)))
            self._response_cache[cache_key] = response

        return response

    async def _search_platform(
        self,
        platform_name: str,
        search_query: str,
        understanding
    ) -> List[RawProfileResult]:
        """Execute search for a single platform and extract raw profiles."""
        try:
            logger.debug("Executing search for [%s]: %s", platform_name, search_query)
            search_results = await search_service.search(
                query=search_query,
                max_results=settings.SEARCH_RESULTS_PER_PLATFORM
            )

            extracted: List[RawProfileResult] = []
            for item in search_results:
                profile = profile_extractor.extract_from_search_result(
                    platform_name=platform_name,
                    result_item=item,
                    understanding=understanding
                )
                if profile:
                    extracted.append(profile)

            return extracted
        except Exception as e:
            logger.warning("Error searching platform %s: %s", platform_name, e)
            return []


prospect_service = ProspectService()
