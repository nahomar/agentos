from __future__ import annotations

import logging
from backend.capabilities.registry import CapabilityProvider, CapabilityResult

logger = logging.getLogger("capabilities.content")


class WebBrowseProvider(CapabilityProvider):
    id = "content.web_browse"
    name = "Browse Web"
    description = "Fetch and read web page content"
    category = "content"

    @property
    def available(self) -> bool:
        return True

    async def execute(self, params: dict) -> CapabilityResult:
        url = params.get("url", "")
        if not url:
            return CapabilityResult(success=False, error="No URL provided")

        try:
            import httpx
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(url, timeout=10)
                return CapabilityResult(success=True, data={
                    "status": resp.status_code,
                    "content": resp.text[:5000],
                    "url": str(resp.url),
                })
        except Exception as e:
            return CapabilityResult(success=False, error=str(e))


class WebSearchProvider(CapabilityProvider):
    id = "content.web_search"
    name = "Web Search"
    description = "Search the web for information"
    category = "content"

    @property
    def available(self) -> bool:
        return True  # Demo mode always available

    async def execute(self, params: dict) -> CapabilityResult:
        query = params.get("query", "")
        api_key = self.config.get("serpapi_key", "")

        if api_key:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://serpapi.com/search",
                        params={"q": query, "api_key": api_key, "num": 5},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results = [
                            {"title": r["title"], "snippet": r.get("snippet", ""), "link": r["link"]}
                            for r in data.get("organic_results", [])[:5]
                        ]
                        return CapabilityResult(success=True, data={"results": results})
            except Exception as e:
                logger.error(f"Search API error: {e}")

        return CapabilityResult(success=True, data={
            "demo": True,
            "results": [{"title": f"Demo result for: {query}", "snippet": "Demo search result", "link": "#"}],
        })
