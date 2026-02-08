"""ACC チャットセッション実行ユースケース。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import uuid4

from acc.adapters.outbound.in_memory_acc_components import (
    InMemoryArtifactMemory,
    InMemoryArtifactRecallAdapter,
    InMemoryEvidenceStoreAdapter,
    TokenOverlapQualificationAdapter,
)
from acc.application.use_cases.acc_multiturn_control_loop import ACCMultiturnControlLoop
from acc.domain.entities.interaction import RecentDialogueTurn, TurnInteractionSignal
from acc.domain.value_objects.ccs import CompressedCognitiveState
from acc.ports.outbound.agent_policy_port import AgentPolicyPort
from acc.ports.outbound.cognitive_compressor_port import CognitiveCompressorPort


class ChatSessionNotFoundError(KeyError):
    """指定セッションが存在しない場合の例外。"""


@dataclass(frozen=True, slots=True)
class ChatCommittedStateSummary:
    """UI/API 向けに公開する CCS 全項目。"""

    episodic_trace: tuple[str, ...]
    semantic_gist: str
    focal_entities: tuple[str, ...]
    relational_map: tuple[str, ...]
    goal_orientation: str
    constraints: tuple[str, ...]
    predictive_cue: tuple[str, ...]
    uncertainty_signal: str
    retrieved_artifacts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChatMechanismSummary:
    """1ターン分の ACC メカニズム要約。"""

    recalled_artifact_count: int
    qualified_artifact_count: int
    committed_state: ChatCommittedStateSummary


@dataclass(frozen=True, slots=True)
class ChatReply:
    """チャット応答の返却値。"""

    session_id: str
    turn_id: int
    reply: str
    memory_tokens: int
    mechanism: ChatMechanismSummary


@dataclass(slots=True)
class _SessionContext:
    """内部セッション状態。"""

    loop: ACCMultiturnControlLoop
    committed_state: CompressedCognitiveState
    turn_id: int
    memory: InMemoryArtifactMemory
    recent_dialogue_turns: list[RecentDialogueTurn]


class ChatSessionUseCase:
    """セッション単位で ACC チャットを実行する。"""

    def __init__(
        self,
        *,
        cognitive_compressor: CognitiveCompressorPort,
        agent_policy: AgentPolicyPort,
        role: str = "assistant",
        tools: Sequence[str] = (),
        recall_limit: int = 5,
        max_sessions: int = 200,
        short_history_turns: int = 2,
    ) -> None:
        """セッション生成に必要な依存と制約を初期化する。"""
        if max_sessions < 1:
            raise ValueError("max_sessions は 1 以上である必要があります。")
        if short_history_turns < 0:
            raise ValueError("short_history_turns は 0 以上である必要があります。")
        self._cognitive_compressor = cognitive_compressor
        self._agent_policy = agent_policy
        self._role = role
        self._tools = tuple(tools)
        self._recall_limit = recall_limit
        self._max_sessions = max_sessions
        self._short_history_turns = short_history_turns
        self._sessions: dict[str, _SessionContext] = {}

    def create_session(self) -> str:
        """新しいチャットセッションを作成して session_id を返す。"""
        if len(self._sessions) >= self._max_sessions:
            self._evict_oldest_session()

        session_id = str(uuid4())
        memory = InMemoryArtifactMemory()
        loop = ACCMultiturnControlLoop(
            artifact_recall=InMemoryArtifactRecallAdapter(memory),
            artifact_qualification=TokenOverlapQualificationAdapter(),
            cognitive_compressor=self._cognitive_compressor,
            agent_policy=self._agent_policy,
            evidence_store=InMemoryEvidenceStoreAdapter(memory),
            recall_limit=self._recall_limit,
            role=self._role,
            tools=self._tools,
        )
        self._sessions[session_id] = _SessionContext(
            loop=loop,
            committed_state=CompressedCognitiveState.empty(),
            turn_id=0,
            memory=memory,
            recent_dialogue_turns=[],
        )
        return session_id

    def send_message(self, *, session_id: str, message: str) -> ChatReply:
        """指定セッションで 1 ターン分のメッセージ処理を行う。"""
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("message は空にできません。")

        session = self._sessions.get(session_id)
        if session is None:
            raise ChatSessionNotFoundError(f"session_id が存在しません: {session_id}")

        next_turn_id = session.turn_id + 1
        interaction_signal = TurnInteractionSignal(
            turn_id=next_turn_id,
            user_input=normalized_message,
            active_goal=session.committed_state.goal_orientation or None,
            active_constraints=session.committed_state.constraints,
            focus_entities=session.committed_state.focal_entities,
            expected_next_steps=session.committed_state.predictive_cue,
        )
        turn_result = session.loop.run_turn(
            interaction_signal=interaction_signal,
            committed_state=session.committed_state,
            recent_dialogue_turns=tuple(session.recent_dialogue_turns),
        )
        session.turn_id = next_turn_id
        session.committed_state = turn_result.committed_state
        self._append_recent_dialogue_turn(
            session=session,
            turn_id=next_turn_id,
            user_input=normalized_message,
            assistant_response=turn_result.decision.response,
        )
        committed_state = turn_result.committed_state
        mechanism = ChatMechanismSummary(
            recalled_artifact_count=len(turn_result.recalled_artifacts),
            qualified_artifact_count=len(turn_result.qualified_artifacts),
            committed_state=ChatCommittedStateSummary(
                episodic_trace=committed_state.episodic_trace,
                semantic_gist=committed_state.semantic_gist,
                focal_entities=committed_state.focal_entities,
                relational_map=committed_state.relational_map,
                goal_orientation=committed_state.goal_orientation,
                constraints=committed_state.constraints,
                predictive_cue=committed_state.predictive_cue,
                uncertainty_signal=committed_state.uncertainty_signal,
                retrieved_artifacts=committed_state.retrieved_artifacts,
            ),
        )

        return ChatReply(
            session_id=session_id,
            turn_id=next_turn_id,
            reply=turn_result.decision.response,
            memory_tokens=_estimate_memory_tokens(session.committed_state),
            mechanism=mechanism,
        )

    def _evict_oldest_session(self) -> None:
        """最大セッション数超過時に最古セッションを削除する。"""
        oldest_session_id = next(iter(self._sessions))
        del self._sessions[oldest_session_id]

    def _append_recent_dialogue_turn(
        self,
        *,
        session: _SessionContext,
        turn_id: int,
        user_input: str,
        assistant_response: str,
    ) -> None:
        """直近参照用の短期対話バッファを更新する。"""
        if self._short_history_turns == 0:
            session.recent_dialogue_turns.clear()
            return

        session.recent_dialogue_turns.append(
            RecentDialogueTurn(
                turn_id=turn_id,
                user_input=user_input,
                assistant_response=assistant_response,
            )
        )
        overflow = len(session.recent_dialogue_turns) - self._short_history_turns
        if overflow > 0:
            del session.recent_dialogue_turns[:overflow]


def _estimate_memory_tokens(state: CompressedCognitiveState) -> int:
    """CCS 文字長ベースの簡易 token 数を返す。"""
    raw_text = " ".join(
        [
            *state.episodic_trace,
            state.semantic_gist,
            *state.focal_entities,
            *state.relational_map,
            state.goal_orientation,
            *state.constraints,
            *state.predictive_cue,
            state.uncertainty_signal,
            *state.retrieved_artifacts,
        ]
    )
    if not raw_text:
        return 0
    return max(1, len(raw_text) // 4)
