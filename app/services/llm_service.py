import json
import logging
import re
import time
from typing import Dict, Any, Optional, Tuple
import httpx

from app.config import settings
from app.schemas import QueryUnderstanding, LocationInfo

logger = logging.getLogger("prospect_discovery.llm")


SYSTEM_PROMPT_QUERY_UNDERSTANDING = """You are an expert search-intent and entity-extraction AI for a prospect discovery engine.
Analyze the user's natural language prospect search query and extract structured parameters in JSON format.

JSON Schema to return:
{
  "interest": "Primary skill, sport, profession, or topic of interest",
  "audience": "Description of the target audience or persona (e.g. Football lovers, Digital marketing agency owners)",
  "location": {
    "city": "City name or null",
    "state": "State/Province name or null",
    "country": "Country name or null"
  },
  "target_type": "individual or business"
}

Rules:
1. Always return valid, pure JSON without any markdown formatting, backticks, or extra commentary.
2. Infer state or country if well known (e.g., 'Washington DC' is in District of Columbia, USA; 'London' is in UK; 'Ahmedabad' is in Gujarat, India; 'Dubai' is in UAE).
3. Distinguish between 'individual' (e.g. football lovers, founders, enthusiasts) and 'business' (e.g. agencies, restaurants).
"""


class LLMService:
    """Multi-provider LLM service with automatic fallback and token tracking."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0

    async def parse_query(self, query: str) -> QueryUnderstanding:
        """
        Understand the natural language query and extract structured parameters.
        Tries primary LLM provider, falls back to alternative or heuristic engine.
        """
        start_time = time.time()
        self.total_requests += 1

        # Attempt primary LLM if API key is provided
        if (self.provider == "groq" or not (settings.GEMINI_API_KEY or settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY)) and settings.GROQ_API_KEY:
            try:
                res = await self._call_groq(query)
                logger.info("Parsed query with Groq in %.2fs", time.time() - start_time)
                return res
            except Exception as e:
                logger.warning("Groq query parsing failed: %s. Trying fallback.", e)

        elif self.provider == "gemini" and settings.GEMINI_API_KEY:
            try:
                res = await self._call_gemini(query)
                logger.info("Parsed query with Gemini in %.2fs", time.time() - start_time)
                return res
            except Exception as e:
                logger.warning("Gemini query parsing failed: %s. Trying fallback.", e)

        elif self.provider == "openai" and settings.OPENAI_API_KEY:
            try:
                res = await self._call_openai(query)
                logger.info("Parsed query with OpenAI in %.2fs", time.time() - start_time)
                return res
            except Exception as e:
                logger.warning("OpenAI query parsing failed: %s. Trying fallback.", e)

        elif self.provider == "claude" and settings.ANTHROPIC_API_KEY:
            try:
                res = await self._call_claude(query)
                logger.info("Parsed query with Claude in %.2fs", time.time() - start_time)
                return res
            except Exception as e:
                logger.warning("Claude query parsing failed: %s. Trying fallback.", e)

        # Fallback to smart heuristic parser (instant, zero cost, completely deterministic)
        logger.info("Using smart heuristic NLP parser for query: '%s'", query)
        return self._heuristic_parse_query(query)

    async def _call_gemini(self, query: str) -> QueryUnderstanding:
        """Call Google Gemini API using REST endpoint."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{SYSTEM_PROMPT_QUERY_UNDERSTANDING}\n\nUser Query: {query}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            # Track token usage if available
            usage = data.get("usageMetadata", {})
            self.total_input_tokens += usage.get("promptTokenCount", 0)
            self.total_output_tokens += usage.get("candidatesTokenCount", 0)

            candidate_text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_json = self._clean_json_text(candidate_text)
            parsed = json.loads(clean_json)
            return self._build_query_understanding(parsed)

    async def _call_openai(self, query: str) -> QueryUnderstanding:
        """Call OpenAI API using REST endpoint."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_QUERY_UNDERSTANDING},
                {"role": "user", "content": f"User Query: {query}"}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            usage = data.get("usage", {})
            self.total_input_tokens += usage.get("prompt_tokens", 0)
            self.total_output_tokens += usage.get("completion_tokens", 0)

            content = data["choices"][0]["message"]["content"]
            clean_json = self._clean_json_text(content)
            parsed = json.loads(clean_json)
            return self._build_query_understanding(parsed)

    async def _call_claude(self, query: str) -> QueryUnderstanding:
        """Call Anthropic Claude API using REST endpoint."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": settings.ANTHROPIC_MODEL,
            "max_tokens": 512,
            "temperature": 0.1,
            "system": SYSTEM_PROMPT_QUERY_UNDERSTANDING,
            "messages": [
                {"role": "user", "content": f"User Query: {query}"}
            ]
        }

        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            usage = data.get("usage", {})
            self.total_input_tokens += usage.get("input_tokens", 0)
            self.total_output_tokens += usage.get("output_tokens", 0)

            content = data["content"][0]["text"]
            clean_json = self._clean_json_text(content)
            parsed = json.loads(clean_json)
            return self._build_query_understanding(parsed)

    async def _call_groq(self, query: str) -> QueryUnderstanding:
        """Call Groq API using AsyncGroq client."""
        import groq
        client = groq.AsyncGroq(api_key=settings.GROQ_API_KEY, timeout=settings.HTTP_TIMEOUT_SECONDS)
        model = settings.GROQ_MODEL or "qwen/qwen3.8-27b"
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_QUERY_UNDERSTANDING},
                {"role": "user", "content": f"User Query: {query}"}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        if resp.usage:
            self.total_input_tokens += resp.usage.prompt_tokens or 0
            self.total_output_tokens += resp.usage.completion_tokens or 0

        content = resp.choices[0].message.content
        clean_json = self._clean_json_text(content)
        parsed = json.loads(clean_json)
        return self._build_query_understanding(parsed)

    def _clean_json_text(self, text: str) -> str:
        """Strip markdown code fence wrappers from JSON output."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _build_query_understanding(self, data: Dict[str, Any]) -> QueryUnderstanding:
        """Assemble validated QueryUnderstanding object from raw parsed dictionary."""
        loc_data = data.get("location") or {}
        location = LocationInfo(
            city=loc_data.get("city"),
            state=loc_data.get("state"),
            country=loc_data.get("country")
        )
        return QueryUnderstanding(
            interest=data.get("interest", "").strip(),
            audience=data.get("audience", "").strip(),
            location=location,
            target_type=data.get("target_type", "individual").strip()
        )

    def _heuristic_parse_query(self, query: str) -> QueryUnderstanding:
        """
        High-precision deterministic rule-based extractor.
        Accurately parses interests, audiences, and locations for global queries.
        """
        q = query.strip()
        q_lower = q.lower()

        # Known cities, states, and country geographic mapping
        location_knowledge = {
            "washington dc": {"city": "Washington DC", "state": "District of Columbia", "country": "USA"},
            "washington d.c.": {"city": "Washington DC", "state": "District of Columbia", "country": "USA"},
            "new york": {"city": "New York", "state": "New York", "country": "USA"},
            "nyc": {"city": "New York", "state": "New York", "country": "USA"},
            "san francisco": {"city": "San Francisco", "state": "California", "country": "USA"},
            "los angeles": {"city": "Los Angeles", "state": "California", "country": "USA"},
            "london": {"city": "London", "state": "Greater London", "country": "UK"},
            "ahmedabad": {"city": "Ahmedabad", "state": "Gujarat", "country": "India"},
            "mumbai": {"city": "Mumbai", "state": "Maharashtra", "country": "India"},
            "delhi": {"city": "Delhi", "state": "Delhi", "country": "India"},
            "bangalore": {"city": "Bangalore", "state": "Karnataka", "country": "India"},
            "bengaluru": {"city": "Bengaluru", "state": "Karnataka", "country": "India"},
            "dubai": {"city": "Dubai", "state": "Dubai", "country": "UAE"},
            "abu dhabi": {"city": "Abu Dhabi", "state": "Abu Dhabi", "country": "UAE"},
            "tokyo": {"city": "Tokyo", "state": "Tokyo", "country": "Japan"},
            "berlin": {"city": "Berlin", "state": "Berlin", "country": "Germany"},
            "paris": {"city": "Paris", "state": "Île-de-France", "country": "France"},
            "toronto": {"city": "Toronto", "state": "Ontario", "country": "Canada"},
            "sydney": {"city": "Sydney", "state": "New South Wales", "country": "Australia"},
        }

        matched_loc = None
        matched_loc_name = ""

        # Check multi-word location matches first
        for loc_key, loc_info in location_knowledge.items():
            if re.search(r"\b" + re.escape(loc_key) + r"\b", q_lower):
                matched_loc = loc_info.copy()
                matched_loc_name = loc_key
                break

        # Fallback to preposition extraction: "in <Location>"
        if not matched_loc:
            in_match = re.search(r"\bin\s+([A-Za-z\s,]+)$", q, re.IGNORECASE)
            if in_match:
                loc_raw = in_match.group(1).strip()
                loc_parts = [p.strip() for p in loc_raw.split(",") if p.strip()]
                if len(loc_parts) == 1:
                    matched_loc = {"city": loc_parts[0], "state": None, "country": None}
                elif len(loc_parts) == 2:
                    matched_loc = {"city": loc_parts[0], "state": None, "country": loc_parts[1]}
                elif len(loc_parts) >= 3:
                    matched_loc = {"city": loc_parts[0], "state": loc_parts[1], "country": loc_parts[2]}

        # If location still None
        if not matched_loc:
            matched_loc = {"city": None, "state": None, "country": None}

        # Check country if explicit in query (e.g., "in USA", "in UK", "in India", "in UAE")
        country_aliases = {
            "usa": "USA", "united states": "USA", "us": "USA",
            "uk": "UK", "united kingdom": "UK",
            "india": "India", "uae": "UAE", "united arab emirates": "UAE",
            "canada": "Canada", "australia": "Australia", "germany": "Germany"
        }
        for alias, c_name in country_aliases.items():
            if re.search(r"\b" + re.escape(alias) + r"\b", q_lower):
                matched_loc["country"] = c_name
                break

        # Extract audience/interest by removing location phrases
        audience_raw = re.sub(r"\bin\s+[A-Za-z\s,]+", "", q, flags=re.IGNORECASE).strip()
        if not audience_raw:
            audience_raw = q

        # Target type identification
        business_indicators = ["agency", "agencies", "restaurant", "restaurants", "company", "companies", "firm", "firms", "shop", "owners"]
        target_type = "individual"
        if any(b in q_lower for b in business_indicators):
            target_type = "business"

        # Interest extraction
        interest = audience_raw
        for suffix in [" lovers", " enthusiasts", " fans", " owners", " founders", " workers", " developers", " players"]:
            if audience_raw.lower().endswith(suffix):
                interest = audience_raw[:-len(suffix)].strip()
                break

        return QueryUnderstanding(
            interest=interest,
            audience=audience_raw,
            location=LocationInfo(
                city=matched_loc.get("city"),
                state=matched_loc.get("state"),
                country=matched_loc.get("country")
            ),
            target_type=target_type
        )


llm_service = LLMService()
