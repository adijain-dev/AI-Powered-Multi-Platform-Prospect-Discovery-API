from abc import ABC, abstractmethod
from typing import Optional, List
from app.schemas import QueryUnderstanding, RawProfileResult
from app.utils.validators import is_valid_platform_profile_url
from app.utils.normalizers import normalize_name, normalize_url, extract_handle_from_url


class BasePlatform(ABC):
    """Abstract base class for all prospect discovery platform integrations."""

    name: str = "Base"

    @abstractmethod
    def generate_search_query(self, understanding: QueryUnderstanding) -> str:
        """
        Generate a platform-targeted search query (e.g. using site dorks and keywords).
        """
        pass

    def is_valid_profile(self, url: str) -> bool:
        """
        Validate whether the URL is a genuine public profile for this platform.
        """
        return is_valid_platform_profile_url(self.name, url)

    def extract_raw_profile(self, title: str, snippet: str, url: str) -> Optional[RawProfileResult]:
        """
        Extract structured profile information from a search result item.
        Returns None if the result does not match profile criteria.
        """
        clean_url = normalize_url(url)
        if not self.is_valid_profile(clean_url):
            return None

        extracted_name = normalize_name(title)
        handle = extract_handle_from_url(clean_url, self.name)

        return RawProfileResult(
            platform=self.name,
            url=clean_url,
            title=title.strip(),
            snippet=snippet.strip(),
            handle=handle,
            extracted_name=extracted_name,
            extracted_location=None,
            emails=[],
            phones=[],
            whatsapp_links=[],
            relevance_score=0.0
        )
