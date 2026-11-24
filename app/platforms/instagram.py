from app.platforms.base import BasePlatform
from app.schemas import QueryUnderstanding


class InstagramPlatform(BasePlatform):
    name: str = "Instagram"

    def generate_search_query(self, understanding: QueryUnderstanding) -> str:
        loc = understanding.location.city or understanding.location.to_location_string()
        topic = understanding.interest or understanding.audience
        parts = ["site:instagram.com", topic]
        if loc:
            parts.append(f'"{loc}"')
        parts.append("-inurl:p/")
        return " ".join(parts)
