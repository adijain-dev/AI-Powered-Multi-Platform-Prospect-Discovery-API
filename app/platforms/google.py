from typing import Optional
from app.platforms.base import BasePlatform
from app.schemas import QueryUnderstanding, RawProfileResult
from app.utils.validators import is_directory_or_aggregator
from app.utils.normalizers import normalize_name, normalize_url


class GooglePlatform(BasePlatform):
    name: str = "Google"

    def generate_search_query(self, understanding: QueryUnderstanding) -> str:
        loc = understanding.location.city or understanding.location.to_location_string()
        topic = understanding.interest or understanding.audience
        parts = [topic, "(inurl:about OR inurl:team OR inurl:bio)"]
        if loc:
            parts.append(f'"{loc}"')
        parts.append("-site:wikipedia.org -site:yelp.com -site:tripadvisor.com")
        return " ".join(parts)

    def is_valid_profile(self, url: str) -> bool:
        if is_directory_or_aggregator(url):
            return False
        u_lower = url.lower()
        if "google." in u_lower or "bing.com" in u_lower or "duckduckgo.com" in u_lower:
            return False
        return True

    def extract_raw_profile(self, title: str, snippet: str, url: str) -> Optional[RawProfileResult]:
        clean_url = normalize_url(url)
        if not self.is_valid_profile(clean_url):
            return None

        name = normalize_name(title)
        if not name or len(name.split()) > 5:
            return None

        return RawProfileResult(
            platform=self.name,
            url=clean_url,
            title=title.strip(),
            snippet=snippet.strip(),
            handle=None,
            extracted_name=name,
            extracted_location=None,
            emails=[],
            phones=[],
            whatsapp_links=[],
            relevance_score=0.0
        )
