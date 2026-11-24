from app.platforms.base import BasePlatform
from app.schemas import QueryUnderstanding


class FacebookPlatform(BasePlatform):
    name: str = "Facebook"

    def generate_search_query(self, understanding: QueryUnderstanding) -> str:
        loc = understanding.location.city or understanding.location.to_location_string()
        topic = understanding.interest or understanding.audience
        parts = ["site:facebook.com", topic]
        if loc:
            parts.append(f'"{loc}"')
        parts.append("-inurl:groups -inurl:events")
        return " ".join(parts)
