from collections.abc import Sequence

import pytest

from acc.adapters.outbound.in_memory_acc_components import (
    EchoAgentPolicyAdapter,
    SimpleCognitiveCompressorAdapter,
)
from acc.application.use_cases.chat_session import (
    ChatSessionNotFoundError,
    ChatSessionUseCase,
)
from acc.domain.entities.interaction import AgentDecision, RecentDialogueTurn, TurnInteractionSignal
from acc.domain.value_objects.ccs import CompressedCognitiveState


class CaptureRecentHistoryPolicyAdapter:
    """decide 時に渡される短期履歴を記録するテスト用 policy。"""

    def __init__(self) -> None:
        """履歴受信記録を初期化する。"""
        self.received_histories: list[tuple[RecentDialogueTurn, ...]] = []

    def decide(
        self,
        interaction_signal: TurnInteractionSignal,
        recent_dialogue_turns: Sequence[RecentDialogueTurn],
        committed_state: CompressedCognitiveState,
        role: str,
        tools: Sequence[str],
    ) -> AgentDecision:
        del committed_state, role, tools
        self.received_histories.append(tuple(recent_dialogue_turns))
        return AgentDecision(response=f"turn={interaction_signal.turn_id}")


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


def test_short_history_turns_keeps_latest_two_turns_by_default_behavior() -> None:
    policy = CaptureRecentHistoryPolicyAdapter()
    use_case = ChatSessionUseCase(
        cognitive_compressor=SimpleCognitiveCompressorAdapter(),
        agent_policy=policy,
        short_history_turns=2,
    )
    session_id = use_case.create_session()

    use_case.send_message(session_id=session_id, message="1つ目")
    use_case.send_message(session_id=session_id, message="2つ目")
    use_case.send_message(session_id=session_id, message="3つ目")
    use_case.send_message(session_id=session_id, message="4つ目")

    assert [len(history) for history in policy.received_histories] == [0, 1, 2, 2]
    assert tuple(turn.turn_id for turn in policy.received_histories[-1]) == (2, 3)


def test_short_history_turns_zero_disables_recent_history() -> None:
    policy = CaptureRecentHistoryPolicyAdapter()
    use_case = ChatSessionUseCase(
        cognitive_compressor=SimpleCognitiveCompressorAdapter(),
        agent_policy=policy,
        short_history_turns=0,
    )
    session_id = use_case.create_session()

    use_case.send_message(session_id=session_id, message="alpha")
    use_case.send_message(session_id=session_id, message="beta")

    assert [len(history) for history in policy.received_histories] == [0, 0]
