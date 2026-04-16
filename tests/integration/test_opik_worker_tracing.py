import pytest
from unittest.mock import MagicMock, patch
from base_agent_system.workers.tasks import run_interaction_branch

def test_run_interaction_branch_is_traced() -> None:
    context = MagicMock()
    mock_obs = MagicMock()
    mock_obs.start_branch_trace.return_value.__enter__.return_value = MagicMock()
    context.runtime_state.observability_service = mock_obs
    
    context.runtime_state.interaction_repository = MagicMock()
    context.runtime_state.workflow_service = MagicMock()
    
    # Mock workflow result
    from unittest.mock import AsyncMock
    context.runtime_state.workflow_service.arun = AsyncMock(return_value={
        "answer": "worker ans",
        "thread_id": "t1",
        "citations": [],
        "debug": {},
        "interaction": {}
    })
    
    import asyncio
    asyncio.run(run_interaction_branch(
        context,
        thread_id="t1",
        interaction_id="i2",
        parent_interaction_id="i1"
    ))
    
    assert mock_obs.start_branch_trace.called
    args, kwargs = mock_obs.start_branch_trace.call_args
    assert kwargs["thread_id"] == "t1"
    assert kwargs["interaction_id"] == "i2"
    assert kwargs["parent_interaction_id"] == "i1"
    assert kwargs["name"] == "worker_interaction_branch"
