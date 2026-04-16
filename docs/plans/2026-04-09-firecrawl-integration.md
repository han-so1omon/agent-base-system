# Firecrawl Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate a self-hosted Firecrawl instance into the Kubernetes deployment and expose its scrape, search, and crawl capabilities as native tools for the agent via direct HTTP requests.

**Architecture:** Firecrawl will be added as an optional component in the `base-agent-system` Helm chart, bundled with a lightweight Redis instance for queue management. The Python application will add a `FirecrawlClient` using the standard library `urllib.request` to avoid introducing new SDK dependencies. Four new tools (`firecrawl_scrape`, `firecrawl_search`, `firecrawl_crawl`, `firecrawl_status`) will be conditionally added to the LangGraph ReAct agent if the `FIRECRAWL_API_URL` configuration is present.

**Tech Stack:** Python, `urllib.request` (zero dependency), LangGraph, Kubernetes/Helm.

---

### Task 1: Extend Application Configuration

**Files:**
- Modify: `src/base_agent_system/config.py`
- Test: `tests/integration/test_config.py`

**Step 1: Write the failing test**

```python
def test_config_loads_firecrawl_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from base_agent_system.config import load_settings
    
    monkeypatch.setenv("BASE_AGENT_SYSTEM_FIRECRAWL_API_URL", "http://firecrawl:3002")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_FIRECRAWL_API_KEY", "fc-key")
    
    settings = load_settings()
    assert settings.firecrawl_api_url == "http://firecrawl:3002"
    assert settings.firecrawl_api_key == "fc-key"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_config.py -q`
Expected: FAIL with "AttributeError: 'Settings' object has no attribute 'firecrawl_api_url'"

**Step 3: Write minimal implementation**

In `src/base_agent_system/config.py`:
```python
@dataclass(frozen=True)
class Settings:
    # ... existing fields ...
    firecrawl_api_url: str = ""
    firecrawl_api_key: str = ""

def load_settings() -> Settings:
    return Settings(
        # ... existing ...
        firecrawl_api_url=_get_env("BASE_AGENT_SYSTEM_FIRECRAWL_API_URL", ""),
        firecrawl_api_key=_get_env("BASE_AGENT_SYSTEM_FIRECRAWL_API_KEY", ""),
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_config.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/config.py tests/integration/test_config.py
git commit -m "feat: add firecrawl config fields"
```

---

### Task 2: Create Zero-Dependency Firecrawl HTTP Client

**Files:**
- Create: `src/base_agent_system/research/firecrawl_client.py`
- Create: `tests/contract/test_firecrawl_client.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/contract/test_firecrawl_client.py -q`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

In `src/base_agent_system/research/firecrawl_client.py`:
```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/contract/test_firecrawl_client.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/research/ tests/contract/test_firecrawl_client.py
git commit -m "feat: add zero-dependency firecrawl client"
```

---

### Task 3: Expose Firecrawl Tools for LangGraph

**Files:**
- Modify: `src/base_agent_system/workflow/agent_tools.py`
- Test: `tests/contract/test_firecrawl_tools.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/contract/test_firecrawl_tools.py -q`
Expected: FAIL with "ImportError"

**Step 3: Write minimal implementation**

In `src/base_agent_system/workflow/agent_tools.py`:
```python
from collections.abc import Callable
from langchain.tools import tool

# (Add to top of file or below existing)
class FirecrawlClientProtocol(Protocol):
    def scrape(self, url: str) -> str: ...
    def search(self, query: str) -> str: ...
    def crawl(self, url: str) -> str: ...
    def crawl_status(self, job_id: str) -> str: ...

def build_firecrawl_scrape_tool(client: FirecrawlClientProtocol) -> Callable[..., str]:
    @tool
    def firecrawl_scrape(url: str) -> str:
        """Scrape a specific URL and return its clean markdown content."""
        try:
            return client.scrape(url)
        except Exception as e:
            return f"Scrape failed: {e}"
    return firecrawl_scrape

def build_firecrawl_search_tool(client: FirecrawlClientProtocol) -> Callable[..., str]:
    @tool
    def firecrawl_search(query: str) -> str:
        """Search the web for a query and return markdown content of top results."""
        try:
            return client.search(query)
        except Exception as e:
            return f"Search failed: {e}"
    return firecrawl_search

def build_firecrawl_crawl_tool(client: FirecrawlClientProtocol) -> Callable[..., str]:
    @tool
    def firecrawl_crawl(url: str) -> str:
        """Start an asynchronous site crawl. Returns a job ID to check status later."""
        try:
            return f"Started crawl. Job ID: {client.crawl(url)}"
        except Exception as e:
            return f"Crawl failed: {e}"
    return firecrawl_crawl

def build_firecrawl_status_tool(client: FirecrawlClientProtocol) -> Callable[..., str]:
    @tool
    def firecrawl_status(job_id: str) -> str:
        """Check the status of an asynchronous crawl using its job ID."""
        try:
            return client.crawl_status(job_id)
        except Exception as e:
            return f"Status check failed: {e}"
    return firecrawl_status
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/contract/test_firecrawl_tools.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/base_agent_system/workflow/agent_tools.py tests/contract/test_firecrawl_tools.py
git commit -m "feat: add firecrawl tools"
```

---

### Task 4: Conditionally Wire Firecrawl Tools in Workflow

**Files:**
- Modify: `src/base_agent_system/workflow/graph.py`
- Test: `tests/integration/test_workflow.py`

**Step 1: Write the failing test**

```python
def test_firecrawl_tools_added_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from base_agent_system.config import load_settings
    from base_agent_system.workflow.graph import build_workflow
    
    monkeypatch.setenv("BASE_AGENT_SYSTEM_FIRECRAWL_API_URL", "http://firecrawl:3002")
    settings = load_settings()
    
    # We assert that the resulting workflow agent has firecrawl tools mapped
    # This requires inspecting the internal `tools` array passed to create_react_agent
    # Or parsing the system prompt.
```
*(Keep test minimal: patch `create_react_agent` and verify tools list contains `firecrawl_scrape`)*

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_workflow.py -q`

**Step 3: Write minimal implementation**

In `src/base_agent_system/workflow/graph.py`:
```python
from base_agent_system.research.firecrawl_client import FirecrawlClient
from base_agent_system.workflow.agent_tools import (
    build_firecrawl_scrape_tool,
    build_firecrawl_search_tool,
    build_firecrawl_crawl_tool,
    build_firecrawl_status_tool,
)

# Inside build_workflow:
    # ... existing tools ...
    if settings.firecrawl_api_url:
        fc_client = FirecrawlClient(settings.firecrawl_api_url, settings.firecrawl_api_key)
        tools.extend([
            build_firecrawl_scrape_tool(fc_client),
            build_firecrawl_search_tool(fc_client),
            build_firecrawl_crawl_tool(fc_client),
            build_firecrawl_status_tool(fc_client),
        ])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_workflow.py -q`

**Step 5: Commit**

```bash
git add src/base_agent_system/workflow/graph.py tests/integration/test_workflow.py
git commit -m "feat: wire firecrawl tools into langgraph agent"
```

---

### Task 5: Kubernetes / Helm Infrastructure

**Files:**
- Create: `infra/helm/base-agent-system/templates/firecrawl.yaml`
- Modify: `infra/helm/base-agent-system/values.yaml`
- Modify: `infra/helm/environments/kind/values.yaml`

**Step 1: Update Values**

In `infra/helm/base-agent-system/values.yaml`:
```yaml
firecrawl:
  enabled: false
  image:
    api: mendableai/firecrawl:latest
    worker: mendableai/firecrawl:latest
```

In `infra/helm/environments/kind/values.yaml`:
```yaml
firecrawl:
  enabled: true
```

**Step 2: Create Firecrawl Manifests**

In `infra/helm/base-agent-system/templates/firecrawl.yaml`:
```yaml
{{- if .Values.firecrawl.enabled -}}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: firecrawl-redis
spec:
  selector:
    matchLabels:
      app: firecrawl-redis
  template:
    metadata:
      labels:
        app: firecrawl-redis
    spec:
      containers:
        - name: redis
          image: redis:alpine
          ports:
            - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: firecrawl-redis
spec:
  ports:
    - port: 6379
  selector:
    app: firecrawl-redis
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: firecrawl-api
spec:
  selector:
    matchLabels:
      app: firecrawl-api
  template:
    metadata:
      labels:
        app: firecrawl-api
    spec:
      containers:
        - name: api
          image: {{ .Values.firecrawl.image.api }}
          env:
            - name: REDIS_URL
              value: redis://firecrawl-redis:6379
            - name: USE_DB_AUTHENTICATION
              value: "false"
          ports:
            - containerPort: 3002
---
apiVersion: v1
kind: Service
metadata:
  name: firecrawl-api
spec:
  ports:
    - port: 3002
  selector:
    app: firecrawl-api
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: firecrawl-worker
spec:
  selector:
    matchLabels:
      app: firecrawl-worker
  template:
    metadata:
      labels:
        app: firecrawl-worker
    spec:
      containers:
        - name: worker
          image: {{ .Values.firecrawl.image.worker }}
          command: ["npm", "run", "workers"]
          env:
            - name: REDIS_URL
              value: redis://firecrawl-redis:6379
{{- end }}
```

*(Also update the `base-agent-system` deployment in `templates/deployment.yaml` to inject the `BASE_AGENT_SYSTEM_FIRECRAWL_API_URL` env var pointing to `http://firecrawl-api:3002` when enabled).*

**Step 3: Verify Infrastructure Smoke Test**

Run local `helm template` check:
```bash
helm template test infra/helm/base-agent-system -f infra/helm/environments/kind/values.yaml > /dev/null
```
Expected: PASS (exit code 0)

**Step 4: Commit**

```bash
git add infra/helm/
git commit -m "feat: add optional self-hosted firecrawl infrastructure"
```

