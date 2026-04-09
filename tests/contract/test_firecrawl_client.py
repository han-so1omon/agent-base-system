import pytest
from unittest.mock import patch, MagicMock
from base_agent_system.research.firecrawl_client import FirecrawlClient

def test_firecrawl_client_scrape_returns_markdown() -> None:
    client = FirecrawlClient(api_url="http://mock", api_key="key")
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"success": true, "data": {"markdown": "# Hello"}}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = client.scrape("https://example.com")
        
        assert result == "# Hello"
