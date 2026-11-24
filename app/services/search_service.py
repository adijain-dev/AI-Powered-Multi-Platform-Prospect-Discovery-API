import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger("prospect_discovery.search")


class SearchService:
    """Multi-backend search discovery service."""

    def __init__(self):
        self._semaphore = asyncio.Semaphore(settings.MAX_PARALLEL_SEARCHES)

    async def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Execute search query across available search backends with automatic fallback.
        Returns a list of dicts: [{'title': str, 'link': str, 'snippet': str}]
        """
        limit = max_results or settings.SEARCH_RESULTS_PER_PLATFORM

        async with self._semaphore:
            # 1. Try Serper API if key is available
            if settings.SERPER_API_KEY:
                try:
                    res = await self._search_serper(query, limit)
                    if res:
                        return res
                except Exception as e:
                    logger.warning("Serper search failed for '%s': %s", query, e)

            # 2. Try Google Custom Search if configured
            if settings.GOOGLE_SEARCH_API_KEY and settings.GOOGLE_SEARCH_CX:
                try:
                    res = await self._search_google_custom(query, limit)
                    if res:
                        return res
                except Exception as e:
                    logger.warning("Google Custom Search failed for '%s': %s", query, e)

            # 3. Try SerpApi if key is available
            if settings.SERPAPI_API_KEY:
                try:
                    res = await self._search_serpapi(query, limit)
                    if res:
                        return res
                except Exception as e:
                    logger.warning("SerpApi search failed for '%s': %s", query, e)

            # 4. Fallback to DuckDuckGo search (zero-config, free, high quality)
            try:
                res = await self._search_ddgs(query, limit)
                if res:
                    return res
            except Exception as e:
                logger.warning("DuckDuckGo search failed for '%s': %s", query, e)

            # 5. Fallback to direct HTML search scraper if library is rate-limited
            try:
                res = await self._search_ddg_html_fallback(query, limit)
                return res
            except Exception as e:
                logger.error("All search providers failed for query '%s': %s", query, e)
                return []

    async def _search_serper(self, query: str, limit: int) -> List[Dict[str, str]]:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": settings.SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {"q": query, "num": limit}
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("organic", [])[:limit]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })
            return results

    async def _search_google_custom(self, query: str, limit: int) -> List[Dict[str, str]]:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.GOOGLE_SEARCH_API_KEY,
            "cx": settings.GOOGLE_SEARCH_CX,
            "q": query,
            "num": min(limit, 10)
        }
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })
            return results

    async def _search_serpapi(self, query: str, limit: int) -> List[Dict[str, str]]:
        url = "https://serpapi.com/search.json"
        params = {
            "api_key": settings.SERPAPI_API_KEY,
            "q": query,
            "num": limit,
            "engine": "google"
        }
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("organic_results", []):
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "")
                })
            return results

    async def _search_ddgs(self, query: str, limit: int) -> List[Dict[str, str]]:
        def _fetch():
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS

                ddgs = DDGS(timeout=settings.HTTP_TIMEOUT_SECONDS)
                raw = list(ddgs.text(query, backend="api", max_results=limit))
            results = []
            for item in raw:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("href", item.get("link", "")),
                    "snippet": item.get("body", item.get("snippet", ""))
                })
            return results

        return await asyncio.to_thread(_fetch)

    async def _search_ddg_html_fallback(self, query: str, limit: int) -> List[Dict[str, str]]:
        """Direct fallback scraper for DuckDuckGo HTML endpoint without library dependencies."""
        url = "https://html.duckduckgo.com/html/"
        data = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, data=data, headers=headers)
            if resp.status_code != 200:
                return []

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for result_elem in soup.find_all("div", class_="result", limit=limit):
                title_elem = result_elem.find("a", class_="result__a")
                snippet_elem = result_elem.find("a", class_="result__snippet")
                if title_elem and title_elem.get("href"):
                    href = title_elem["href"]
                    # Clean duckduckgo redirect url if necessary
                    if "uddg=" in href:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        href = parsed.get("uddg", [href])[0]

                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "link": href,
                        "snippet": snippet_elem.get_text(strip=True) if snippet_elem else ""
                    })
            return results


search_service = SearchService()
