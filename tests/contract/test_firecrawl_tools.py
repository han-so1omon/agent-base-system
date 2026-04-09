import pytest
from unittest.mock import MagicMock
from base_agent_system.workflow.agent_tools import build_firecrawl_scrape_tool

def test_firecrawl_scrape_tool_returns_markdown() -> None:
    mock_client = MagicMock()
    mock_client.scrape.return_value = "# Mocked Markdown"
    
    tool = build_firecrawl_scrape_tool(mock_client)
    result = tool.invoke({"url": "https://example.com"})
    
    assert result == "# Mocked Markdown"
    mock_client.scrape.assert_called_once_with("https://example.com")
