"""Chat UI adapter and embedded fallback page."""

from __future__ import annotations

from pathlib import Path
import json
import mimetypes
import os
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from base_agent_system.api.routes_interact import run_interaction


router = APIRouter()


class _ChatPart(BaseModel):
    type: str
    text: str | None = None


class _ChatMessage(BaseModel):
    role: str
    parts: list[_ChatPart] = []
    content: str | None = None


class _ChatRequest(BaseModel):
    threadId: str | None = None
    messages: list[_ChatMessage]


@router.get("/chat", response_class=HTMLResponse)
def chat_page() -> HTMLResponse:
    asset = _chat_asset_path("index.html")
    if asset.exists():
        return HTMLResponse(asset.read_text())
    return HTMLResponse(_EMBEDDED_CHAT_HTML)


@router.get("/chat/{asset_path:path}")
def chat_asset(asset_path: str) -> Response:
    asset = _chat_asset_path(asset_path)
    if not asset.exists() or not asset.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat asset not found")
    media_type, _ = mimetypes.guess_type(asset.name)
    return Response(asset.read_bytes(), media_type=media_type or "application/octet-stream")


@router.post("/api/chat")
def chat_api(payload: _ChatRequest, request: Request) -> dict[str, Any]:
    with request.app.state.runtime_state.observability_service.start_span(
        name="POST /api/chat",
        metadata={"thread_id": payload.threadId or ""},
    ):
        query = _latest_user_text(payload.messages)
        if not query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="missing user message text",
            )

        thread_id = payload.threadId or str(uuid4())
        try:
            result = run_interaction(
                workflow_service=request.app.state.runtime_state.workflow_service,
                thread_id=thread_id,
                messages=_normalize_messages(payload.messages),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
            ) from exc

        if _prefers_text_stream(request):
            return StreamingResponse(
                _stream_answer_text(result["answer"]),
                media_type="text/plain; charset=utf-8",
                headers={
                    "x-thread-id": str(result["thread_id"]),
                    "x-citations": json.dumps(result["citations"]),
                    "x-debug": json.dumps(result["debug"]),
                    "x-interaction": json.dumps(result.get("interaction", {})),
                },
            )

        return {
            "id": result["thread_id"],
            "messages": [
                {
                    "id": "assistant-message",
                    "role": "assistant",
                    "parts": [{"type": "text", "text": result["answer"]}],
                    "metadata": {
                        "thread_id": result["thread_id"],
                        "citations": result["citations"],
                        "debug": result["debug"],
                        **(
                            {"spawn": result.get("interaction", {}).get("spawn")}
                            if result.get("interaction", {}).get("spawn")
                            else {}
                        ),
                    },
                }
            ],
        }



def _latest_user_text(messages: list[_ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role != "user":
            continue
        parts_text = "\n".join(part.text or "" for part in message.parts if part.type == "text").strip()
        if parts_text:
            return parts_text
        if message.content and message.content.strip():
            return message.content.strip()
    return ""


def _normalize_messages(messages: list[_ChatMessage]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in messages:
        parts_text = "\n".join(part.text or "" for part in message.parts if part.type == "text").strip()
        content = parts_text or (message.content or "").strip()
        if not content:
            continue
        normalized.append({"role": message.role, "content": content})
    return normalized


def _prefers_text_stream(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/plain" in accept.lower()


def _stream_answer_text(answer: str):
    yield answer


def _chat_asset_path(asset_path: str) -> Path:
    return Path(os.getenv("BASE_AGENT_SYSTEM_APP_ROOT", "/app")) / "web-static" / asset_path


_EMBEDDED_CHAT_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Base Agent System Chat</title>
  <style>
    :root { color-scheme: dark; }
    body { margin: 0; background: #0b1015; color: #f2ecdf; font-family: Georgia, serif; }
    main { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
    section { width: min(720px, 100%); border: 1px solid rgba(211,190,142,0.22); padding: 28px; background: rgba(16,20,24,0.9); }
    h1 { margin: 0 0 12px; font-size: clamp(2rem, 5vw, 4rem); font-weight: 500; }
    p { color: #a6adb4; line-height: 1.7; }
    code { color: #f0c96b; }
  </style>
</head>
<body>
  <main>
    <section>
      <div style="color:#d3be8e;letter-spacing:.24em;text-transform:uppercase;font-size:12px;">Base Agent System</div>
      <h1>Base Agent System Chat</h1>
      <p>The embedded fallback UI is active. Build and package the <code>web/</code> app to replace this page with the full Vercel AI SDK operator chat.</p>
    </section>
  </main>
</body>
</html>
"""
