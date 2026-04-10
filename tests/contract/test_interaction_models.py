from __future__ import annotations

from base_agent_system.interactions.models import (
    Interaction,
    InteractionArtifactReference,
    InteractionEvent,
    InteractionEventPage,
    InteractionPage,
    InteractionThreadSummary,
)


def test_interaction_supports_tree_identity_and_cached_projection_fields() -> None:
    interaction = Interaction(
        id="interaction-123",
        thread_id="thread-123",
        parent_interaction_id="interaction-root",
        kind="deep_agent",
        status="running",
        created_at="2026-04-09T00:00:00Z",
        updated_at="2026-04-09T00:01:00Z",
        last_event_at="2026-04-09T00:01:00Z",
        latest_display_event_id="event-456",
        child_count=2,
        metadata={"reporting_target": "parent"},
    )

    assert interaction.parent_interaction_id == "interaction-root"
    assert interaction.status == "running"
    assert interaction.last_event_at == "2026-04-09T00:01:00Z"
    assert interaction.latest_display_event_id == "event-456"
    assert interaction.child_count == 2
    assert interaction.metadata == {"reporting_target": "parent"}


def test_interaction_event_supports_event_sourced_content_and_artifacts() -> None:
    artifact = InteractionArtifactReference(
        artifact_id="artifact-123",
        storage_backend="local",
        storage_uri="file:///tmp/report.md",
        media_type="text/markdown",
        logical_role="summary",
        checksum="sha256:abc",
        metadata={"title": "Report"},
    )
    event = InteractionEvent(
        id="event-123",
        interaction_id="interaction-123",
        event_type="checkpoint",
        created_at="2026-04-09T00:02:00Z",
        content="Visited three sources and narrowed the scope.",
        is_display_event=True,
        status="running",
        artifacts=[artifact],
        metadata={"tool_name": "firecrawl_search"},
    )

    assert event.content == "Visited three sources and narrowed the scope."
    assert event.artifacts == [artifact]
    assert event.metadata == {"tool_name": "firecrawl_search"}
    assert event.is_display_event is True


def test_interaction_pages_are_projection_driven() -> None:
    event = InteractionEvent(
        id="event-123",
        interaction_id="interaction-123",
        event_type="message_authored",
        created_at="2026-04-09T00:02:00Z",
        content="I started a deeper investigation.",
        is_display_event=True,
        status="completed",
    )
    interaction = Interaction(
        id="interaction-123",
        thread_id="thread-123",
        parent_interaction_id=None,
        kind="agent_run",
        status="completed",
        created_at="2026-04-09T00:00:00Z",
        updated_at="2026-04-09T00:02:00Z",
        last_event_at="2026-04-09T00:02:00Z",
        latest_display_event_id="event-123",
        child_count=1,
        latest_display_event=event,
    )

    page = InteractionPage(items=[interaction], has_more=False, next_before=None)
    event_page = InteractionEventPage(items=[event], has_more=False, next_before=None)
    thread = InteractionThreadSummary(thread_id="thread-123", preview="Deep investigation")

    assert page.items[0].latest_display_event is event
    assert event_page.items[0].event_type == "message_authored"
    assert thread.preview == "Deep investigation"
