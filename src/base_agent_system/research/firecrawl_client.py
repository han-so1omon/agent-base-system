"""Firecrawl client with async-first API."""

from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import Any


class FirecrawlClient:
    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    async def _request_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._request_json_sync, endpoint, payload)

    async def _get_json(self, endpoint: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_json_sync, endpoint)

    def _request_json_sync(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_json_sync(self, endpoint: str) -> dict[str, Any]:
        url = f"{self.api_url}{endpoint}"
        request = urllib.request.Request(url, method="GET")
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    async def ascrape(self, url: str) -> str:
        result = await self._request_json("/v1/scrape", {"url": url, "formats": ["markdown"]})
        return result.get("data", {}).get("markdown", "No content found.")

    async def asearch(self, query: str) -> str:
        result = await self._request_json(
            "/v1/search",
            {"query": query, "pageOptions": {"fetchPageContent": True}},
        )
        if not result.get("success"):
            return "Search failed."
        rows = result.get("data", [])
        return "\n\n".join(f"URL: {row.get('url')}\nContent: {row.get('markdown')}" for row in rows[:3])

    async def acrawl(self, url: str) -> str:
        result = await self._request_json("/v1/crawl", {"url": url, "limit": 10})
        return result.get("id", "")

    async def acrawl_status(self, job_id: str) -> str:
        result = await self._get_json(f"/v1/crawl/{job_id}")
        status = result.get("status", "unknown")
        if status != "completed":
            return f"Crawl status: {status}"
        data = result.get("data", [])
        urls = ", ".join(item.get("url") for item in data)
        return f"Crawl completed. Found {len(data)} pages. URLs: {urls}"

    def scrape(self, url: str) -> str:
        return asyncio.run(self.ascrape(url))

    def search(self, query: str) -> str:
        return asyncio.run(self.asearch(query))

    def crawl(self, url: str) -> str:
        return asyncio.run(self.acrawl(url))

    def crawl_status(self, job_id: str) -> str:
        return asyncio.run(self.acrawl_status(job_id))
