import pytest

from acc.adapters.outbound.in_memory_acc_components import (
    EchoAgentPolicyAdapter,
    SimpleCognitiveCompressorAdapter,
)
from acc.application.use_cases.chat_session import (
    ChatSessionNotFoundError,
    ChatSessionUseCase,
)


def _build_use_case(*, max_sessions: int = 200) -> ChatSessionUseCase:
    return ChatSessionUseCase(
        cognitive_compressor=SimpleCognitiveCompressorAdapter(),
        agent_policy=EchoAgentPolicyAdapter(),
        max_sessions=max_sessions,
    )


def test_create_session_and_send_message_returns_reply() -> None:
    use_case = _build_use_case()
    session_id = use_case.create_session()

    first_reply = use_case.send_message(session_id=session_id, message="Nginx 502 の対処を教えて")
    second_reply = use_case.send_message(session_id=session_id, message="次に見るべき指標は？")

    assert first_reply.session_id == session_id
    assert first_reply.turn_id == 1
    assert first_reply.reply
    assert first_reply.memory_tokens >= 0
    assert first_reply.mechanism.recalled_artifact_count >= 0
    assert first_reply.mechanism.qualified_artifact_count >= 0
    assert first_reply.mechanism.committed_state.episodic_trace
    assert first_reply.mechanism.committed_state.semantic_gist
    assert isinstance(first_reply.mechanism.committed_state.focal_entities, tuple)
    assert isinstance(first_reply.mechanism.committed_state.relational_map, tuple)
    assert first_reply.mechanism.committed_state.goal_orientation
    assert first_reply.mechanism.committed_state.predictive_cue
    assert first_reply.mechanism.committed_state.uncertainty_signal in {"低", "中"}
    assert "タスク整合性" in first_reply.mechanism.committed_state.goal_orientation
    assert first_reply.mechanism.committed_state.predictive_cue[0].startswith("次に")

    assert second_reply.turn_id == 2
    assert second_reply.reply
    assert second_reply.mechanism.recalled_artifact_count >= 0


def test_send_message_raises_for_unknown_session() -> None:
    use_case = _build_use_case()

    with pytest.raises(ChatSessionNotFoundError):
        use_case.send_message(session_id="unknown", message="hello")


def test_oldest_session_is_evicted_when_limit_exceeded() -> None:
    use_case = _build_use_case(max_sessions=1)
    first_session = use_case.create_session()
    second_session = use_case.create_session()

    assert first_session != second_session

    with pytest.raises(ChatSessionNotFoundError):
        use_case.send_message(session_id=first_session, message="still there?")
