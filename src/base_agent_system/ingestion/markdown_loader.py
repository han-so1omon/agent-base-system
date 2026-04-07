"""Minimal markdown file discovery and normalization."""

from pathlib import Path

from llama_index.core import Document

from base_agent_system.ingestion.models import MarkdownDocument


def load_markdown_documents(directory: Path) -> list[MarkdownDocument]:
    return [
        _load_markdown_document(path)
        for path in sorted(directory.rglob("*.md"))
        if path.is_file()
    ]


def _load_markdown_document(path: Path) -> MarkdownDocument:
    raw_content = path.read_text(encoding="utf-8")
    content = raw_content.strip()
    title = _extract_title(content, path)
    return MarkdownDocument(
        source_path=path,
        title=title,
        content=content,
        llama_document=Document(
            text=content,
            metadata={"path": str(path), "title": title},
        ),
    )


def _extract_title(content: str, path: Path) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.stem
