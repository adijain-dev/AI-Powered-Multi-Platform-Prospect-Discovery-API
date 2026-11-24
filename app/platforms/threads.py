from app.platforms.base import BasePlatform
from app.schemas import QueryUnderstanding


class ThreadsPlatform(BasePlatform):
    name: str = "Threads"

    def generate_search_query(self, understanding: QueryUnderstanding) -> str:
        loc = understanding.location.city or understanding.location.to_location_string()
        topic = understanding.interest or understanding.audience
        parts = ["site:threads.net/@", topic]
        if loc:
            parts.append(f'"{loc}"')
        return " ".join(parts)
