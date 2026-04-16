from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from base_agent_system.research.firecrawl_client import FirecrawlClient


@pytest.mark.asyncio
async def test_firecrawl_client_async_scrape_returns_markdown() -> None:
    client = FirecrawlClient(api_url="http://mock", api_key="key")
    client._request_json = AsyncMock(return_value={"success": True, "data": {"markdown": "# Hello"}})

    result = await client.ascrape("https://example.com")

    assert result == "# Hello"


@pytest.mark.asyncio
async def test_firecrawl_client_async_search_formats_top_results() -> None:
    client = FirecrawlClient(api_url="http://mock", api_key="key")
    client._request_json = AsyncMock(
        return_value={
            "success": True,
            "data": [
                {"url": "https://a.test", "markdown": "A"},
                {"url": "https://b.test", "markdown": "B"},
            ],
        }
    )

    result = await client.asearch("agent systems")

    assert "https://a.test" in result
    assert "Content: A" in result
    client._request_json.assert_awaited_once_with(
        "/v1/search",
        {"query": "agent systems", "scrapeOptions": {"formats": ["markdown"]}},
    )


@pytest.mark.asyncio
async def test_firecrawl_client_async_crawl_status_reports_completion() -> None:
    client = FirecrawlClient(api_url="http://mock", api_key="key")
    client._get_json = AsyncMock(
        return_value={
            "status": "completed",
            "data": [{"url": "https://a.test"}, {"url": "https://b.test"}],
        }
    )

    result = await client.acrawl_status("job-123")

    assert result == "Crawl completed. Found 2 pages. URLs: https://a.test, https://b.test"


def test_firecrawl_client_sync_methods_delegate_to_async_api() -> None:
    client = FirecrawlClient(api_url="http://mock", api_key="key")
    client.ascrape = AsyncMock(return_value="# Hello")

    result = client.scrape("https://example.com")

    assert result == "# Hello"
