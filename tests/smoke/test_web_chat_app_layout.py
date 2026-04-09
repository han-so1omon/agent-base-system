from pathlib import Path


def test_web_chat_app_layout_supports_ai_sdk_adapter() -> None:
    package_json = Path("web/package.json")
    page = Path("web/app/page.tsx")
    next_config = Path("web/next.config.ts")
    env_example = Path("web/.env.local.example")

    assert package_json.exists()
    assert page.exists()
    assert next_config.exists()
    assert env_example.exists()

    package_text = package_json.read_text()
    page_text = page.read_text()
    next_config_text = next_config.read_text()
    env_text = env_example.read_text()

    assert '"next"' in package_text
    assert '"react"' in package_text
    assert '"@ai-sdk/react"' in package_text
    assert '"ai"' in package_text
    assert "useChat" in page_text
    assert "/api/chat" in page_text
    assert '"/threads"' in page_text or "'/threads'" in page_text
    assert "Recent Threads" in page_text
    assert "New thread starts on first message" in page_text
    assert "streamProtocol: 'text'" in page_text or 'streamProtocol: "text"' in page_text
    assert "threadId" in page_text
    assert "output: 'export'" in next_config_text
    assert "basePath: '/chat'" in next_config_text
    assert "BASE_AGENT_SYSTEM_API_URL=" in env_text


def test_web_chat_app_keeps_history_visible_during_live_turns() -> None:
    page_text = Path("web/app/page.tsx").read_text()

    assert "mergeMessages(historyMessages, liveMessages)" in page_text
    assert "if (liveMessages.length > 0)" not in page_text


def test_web_chat_app_uses_bounded_scrollable_history_pane() -> None:
    page_text = Path("web/app/page.tsx").read_text()

    assert "minHeight: 0" in page_text
    assert page_text.count("overflowY: 'auto'") >= 2
    assert page_text.count("gridTemplateRows: 'auto 1fr auto'") >= 2
