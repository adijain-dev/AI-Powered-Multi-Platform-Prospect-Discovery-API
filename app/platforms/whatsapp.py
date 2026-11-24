from typing import Optional
from app.platforms.base import BasePlatform
from app.schemas import QueryUnderstanding, RawProfileResult
from app.utils.validators import is_valid_whatsapp_link
from app.utils.normalizers import normalize_name, normalize_url


class WhatsAppPlatform(BasePlatform):
    name: str = "WhatsApp"

    def generate_search_query(self, understanding: QueryUnderstanding) -> str:
        loc = understanding.location.city or understanding.location.to_location_string()
        topic = understanding.interest or understanding.audience
        parts = ["(site:wa.me OR inurl:wa.me)", topic]
        if loc:
            parts.append(f'"{loc}"')
        return " ".join(parts)

    def is_valid_profile(self, url: str) -> bool:
        return is_valid_whatsapp_link(url)

    def extract_raw_profile(self, title: str, snippet: str, url: str) -> Optional[RawProfileResult]:
        clean_url = normalize_url(url)
        if not self.is_valid_profile(clean_url):
            return None

        name = normalize_name(title)
        return RawProfileResult(
            platform=self.name,
            url=clean_url,
            title=title.strip(),
            snippet=snippet.strip(),
            handle=None,
            extracted_name=name or "WhatsApp Contact",
            extracted_location=None,
            emails=[],
            phones=[],
            whatsapp_links=[clean_url],
            relevance_score=0.0
        )
