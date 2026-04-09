import json
import urllib.request
from typing import Any

class FirecrawlClient:
    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def _request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
            
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get(self, endpoint: str) -> dict[str, Any]:
        url = f"{self.api_url}{endpoint}"
        req = urllib.request.Request(url, method="GET")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
            
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def scrape(self, url: str) -> str:
        res = self._request("/v1/scrape", {"url": url, "formats": ["markdown"]})
        return res.get("data", {}).get("markdown", "No content found.")

    def search(self, query: str) -> str:
        res = self._request("/v1/search", {"query": query, "pageOptions": {"fetchPageContent": True}})
        if not res.get("success"):
            return "Search failed."
        results = res.get("data", [])
        return "\n\n".join(f"URL: {r.get('url')}\nContent: {r.get('markdown')}" for r in results[:3])

    def crawl(self, url: str) -> str:
        res = self._request("/v1/crawl", {"url": url, "limit": 10})
        return res.get("id", "")

    def crawl_status(self, job_id: str) -> str:
        res = self._get(f"/v1/crawl/{job_id}")
        status = res.get("status", "unknown")
        if status != "completed":
            return f"Crawl status: {status}"
        data = res.get("data", [])
        return f"Crawl completed. Found {len(data)} pages. URLs: " + ", ".join(d.get('url') for d in data)
