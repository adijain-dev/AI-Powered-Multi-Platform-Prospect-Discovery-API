import re
import logging
from typing import List
from app.schemas import RawProfileResult, QueryUnderstanding
from app.utils.validators import is_directory_or_aggregator

logger = logging.getLogger("prospect_discovery.relevance")


class RelevanceService:
    """Evaluates prospect authenticity, interest match, location relevance, and audience alignment."""

    def filter_and_score(
        self,
        profiles: List[RawProfileResult],
        understanding: QueryUnderstanding,
        min_threshold: float = 0.30
    ) -> List[RawProfileResult]:
        """
        Score each discovered profile and filter out irrelevant or generic results.
        """
        scored_profiles: List[RawProfileResult] = []

        for p in profiles:
            score = self.calculate_relevance(p, understanding)
            p.relevance_score = score
            if score >= min_threshold:
                scored_profiles.append(p)
            else:
                logger.debug(
                    "Profile '%s' (%s) filtered out due to low relevance score: %.2f",
                    p.extracted_name or p.title, p.url, score
                )

        # Sort descending by relevance score
        scored_profiles.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_profiles

    def calculate_relevance(self, profile: RawProfileResult, understanding: QueryUnderstanding) -> float:
        """
        Compute weighted relevance score between 0.0 and 1.0.
        Factors:
        - Profile Authenticity & Structure (25%)
        - Interest / Topic Match (35%)
        - Location Match (25%)
        - Contact / Actionable Link Evidence (15%)
        """
        # Hard rejection for generic aggregators or directory listing pages
        if is_directory_or_aggregator(profile.url):
            return 0.0

        title_lower = profile.title.lower()
        snippet_lower = profile.snippet.lower()
        combined_text = f"{title_lower} {snippet_lower} {profile.url.lower()}"

        score = 0.0

        # 1. Profile Authenticity (0.0 to 0.25)
        # Genuine personal / company profile URLs
        if profile.platform in {"LinkedIn", "X", "Instagram", "Threads", "YouTube", "Facebook", "WhatsApp"}:
            score += 0.25
        elif profile.platform == "Google" and profile.extracted_name:
            # Personal website or portfolio
            score += 0.20

        # 2. Interest / Topic Relevance (0.0 to 0.35)
        interest_tokens = [t.lower() for t in re.findall(r"\w+", understanding.interest) if len(t) > 2]
        audience_tokens = [t.lower() for t in re.findall(r"\w+", understanding.audience) if len(t) > 2]
        all_topic_tokens = set(interest_tokens + audience_tokens)

        if all_topic_tokens:
            matches = sum(1 for token in all_topic_tokens if token in combined_text)
            match_ratio = min(matches / max(len(all_topic_tokens), 1), 1.0)
            score += match_ratio * 0.35
        else:
            score += 0.20

        # 3. Location Relevance (0.0 to 0.25)
        loc = understanding.location
        loc_score = 0.0
        loc_components = [p.lower() for p in [loc.city, loc.state, loc.country] if p]

        if loc_components:
            for comp in loc_components:
                if comp in combined_text:
                    loc_score += 0.12
            score += min(loc_score, 0.25)
        else:
            # Query did not specify location, don't penalize
            score += 0.25

        # 4. Actionable Evidence & Verified Links (0.0 to 0.15)
        if profile.emails or profile.phones or profile.whatsapp_links:
            score += 0.15
        elif profile.handle:
            score += 0.10
        else:
            score += 0.05

        # Penalize if title looks like a generic article or search listing
        generic_markers = [
            "top 10", "best", "list of", "directory", "reviews of",
            "jobs in", "vacancies", "find near you", "search results"
        ]
        if any(marker in title_lower for marker in generic_markers):
            score *= 0.3

        return round(min(score, 1.0), 3)


relevance_service = RelevanceService()
