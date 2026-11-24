from app.platforms.base import BasePlatform
from app.schemas import QueryUnderstanding


class YouTubePlatform(BasePlatform):
    name: str = "YouTube"

    def generate_search_query(self, understanding: QueryUnderstanding) -> str:
        loc = understanding.location.city or understanding.location.to_location_string()
        topic = understanding.interest or understanding.audience
        parts = ["site:youtube.com/@", topic]
        if loc:
            parts.append(f'"{loc}"')
        return " ".join(parts)
