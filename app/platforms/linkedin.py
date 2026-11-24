from app.platforms.base import BasePlatform
from app.schemas import QueryUnderstanding


class LinkedInPlatform(BasePlatform):
    name: str = "LinkedIn"

    def generate_search_query(self, understanding: QueryUnderstanding) -> str:
        loc = understanding.location.city or understanding.location.to_location_string()
        topic = understanding.interest or understanding.audience
        parts = ["site:linkedin.com/in", topic]
        if loc:
            parts.append(f'"{loc}"')
        return " ".join(parts)
