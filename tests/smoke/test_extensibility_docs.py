from pathlib import Path


def test_extensibility_docs_describe_supported_seams_and_non_goals() -> None:
    readme = Path("README.md")
    local_dev = Path("docs/runbooks/local-development.md")
    troubleshooting = Path("docs/runbooks/troubleshooting.md")

    assert readme.exists()
    assert local_dev.exists()
    assert troubleshooting.exists()

    text = "\n".join(
        [
            readme.read_text(),
            local_dev.read_text(),
            troubleshooting.read_text(),
        ]
    )

    assert "workflow" in text.lower()
    assert "ingestion" in text.lower()
    assert "retrieval" in text.lower()
    assert "api" in text.lower()
    assert "cli" in text.lower()
    assert "explicit registration" in text.lower()
    assert "register_cli_command_contributor" in text
    assert "no auto-discovery" in text.lower()
    assert "no out-of-process plugins" in text.lower()
    assert "no arbitrary workflow graph mutation" in text.lower()
