from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from base_agent_system.workflow.agent_tools import build_firecrawl_scrape_tool


def test_firecrawl_scrape_tool_returns_markdown() -> None:
    mock_client = MagicMock()
    mock_client.scrape.return_value = "# Mocked Markdown"

    tool = build_firecrawl_scrape_tool(mock_client)
    result = tool.invoke({"url": "https://example.com"})

    assert result == "# Mocked Markdown"
    mock_client.scrape.assert_called_once_with("https://example.com")


@pytest.mark.asyncio
async def test_firecrawl_scrape_tool_async_entrypoint_uses_async_client() -> None:
    mock_client = MagicMock()
    mock_client.ascrape = AsyncMock(return_value="# Async Markdown")

    tool = build_firecrawl_scrape_tool(mock_client)
    result = await tool.ainvoke({"url": "https://example.com"})

    assert result == "# Async Markdown"
    mock_client.ascrape.assert_awaited_once_with("https://example.com")
