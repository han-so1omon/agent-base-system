from __future__ import annotations

from fastapi.testclient import TestClient
from pathlib import Path
import pytest

from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv(
        "BASE_AGENT_SYSTEM_POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/app",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")


def test_get_chat_serves_embedded_web_ui(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    from base_agent_system.api.app import create_app

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    with TestClient(
        create_app(
            initialize_dependencies=False,
            memory_backend=_InMemoryGraphitiBackend(),
        )
    ) as client:
        response = client.get("/chat")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Base Agent System Chat" in response.text


def test_get_chat_serves_packaged_static_assets_from_app_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    app_root = tmp_path / "app-root"
    web_static = app_root / "web-static"
    next_dir = web_static / "_next" / "static"
    next_dir.mkdir(parents=True)
    (web_static / "index.html").write_text("<html><body>packaged chat ui</body></html>")
    (next_dir / "app.js").write_text("console.log('chat asset');")

    monkeypatch.setenv("BASE_AGENT_SYSTEM_APP_ROOT", str(app_root))

    from base_agent_system.api.app import create_app

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    with TestClient(
        create_app(
            initialize_dependencies=False,
            memory_backend=_InMemoryGraphitiBackend(),
        )
    ) as client:
        page_response = client.get("/chat")
        asset_response = client.get("/chat/_next/static/app.js")

    assert page_response.status_code == 200
    assert "packaged chat ui" in page_response.text
    assert asset_response.status_code == 200
    assert asset_response.text == "console.log('chat asset');"
