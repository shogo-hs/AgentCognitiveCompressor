"""ACC コアループ向けの in-memory アダプタ群。"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import AgentDecision, RecentDialogueTurn, TurnInteractionSignal
from acc.domain.value_objects.ccs import CompressedCognitiveState
from acc.ports.outbound.agent_policy_port import AgentPolicyPort
from acc.ports.outbound.artifact_qualification_port import ArtifactQualificationPort
from acc.ports.outbound.artifact_recall_port import ArtifactRecallPort
from acc.ports.outbound.cognitive_compressor_port import CognitiveCompressorPort
from acc.ports.outbound.evidence_store_port import EvidenceStorePort

_ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
_JAPANESE_TOKEN_PATTERN = re.compile(r"[ぁ-んァ-ヶー一-龠々〆〤]+")


@dataclass(frozen=True, slots=True)
class StoredTurnEvidence:
    """永続化したターン証拠の記録。"""

    interaction_signal: TurnInteractionSignal
    decision: AgentDecision
    artifact_id: str


class InMemoryArtifactMemory:
    """Artifact とターン証拠を保持する簡易ストア。"""

    def __init__(
        self,
        seed_artifacts: Sequence[Artifact] = (),
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        """初期 Artifact 群と現在時刻取得関数を受け取る。"""
        self._artifacts: list[Artifact] = list(seed_artifacts)
        self._turn_records: list[StoredTurnEvidence] = []
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    @property
    def turn_records(self) -> tuple[StoredTurnEvidence, ...]:
        """保存済みターン証拠を返す。"""
        return tuple(self._turn_records)

    def list_artifacts(self) -> tuple[Artifact, ...]:
        """現時点の Artifact 一覧を返す。"""
        return tuple(self._artifacts)

    def append_turn_evidence_artifact(
        self,
        interaction_signal: TurnInteractionSignal,
        decision: AgentDecision,
        source: str,
    ) -> Artifact:
        """ターン入出力を Artifact 化して保存する。"""
        timestamp = self._now_provider()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        artifact = Artifact(
            artifact_id=f"{source}-{interaction_signal.turn_id}-{len(self._turn_records) + 1}",
            content=f"user:{interaction_signal.user_input}\nassistant:{decision.response}",
            source=source,
            created_at=timestamp,
        )
        self._artifacts.append(artifact)
        self._turn_records.append(
            StoredTurnEvidence(
                interaction_signal=interaction_signal,
                decision=decision,
                artifact_id=artifact.artifact_id,
            )
        )
        return artifact


class InMemoryArtifactRecallAdapter(ArtifactRecallPort):
    """簡易トークン重なりで Artifact 想起を行うアダプタ。"""

    def __init__(self, memory: InMemoryArtifactMemory) -> None:
        """共有メモリを受け取って初期化する。"""
        self._memory = memory

    def recall_candidate_artifacts(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        limit: int,
    ) -> Sequence[Artifact]:
        """入力との重なりを優先して候補 Artifact を返す。"""
        del committed_state  # Phase 1 では入力ベースの簡易想起に限定する。
        query_tokens = _normalize_tokens(interaction_signal.user_input)
        scored_artifacts: list[tuple[int, float, Artifact]] = []

        for artifact in self._memory.list_artifacts():
            overlap = len(query_tokens & _normalize_tokens(artifact.content))
            scored_artifacts.append((overlap, artifact.created_at.timestamp(), artifact))

        scored_artifacts.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = [artifact for score, _, artifact in scored_artifacts if score > 0]
        return tuple(selected[:limit])


class TokenOverlapQualificationAdapter(ArtifactQualificationPort):
    """トークン重なりで Artifact の採用可否を判定するアダプタ。"""

    def is_decision_relevant(
        self,
        artifact: Artifact,
        committed_state: CompressedCognitiveState,
        interaction_signal: TurnInteractionSignal,
    ) -> bool:
        """入力または既存制約と関連する Artifact のみ採用する。"""
        if artifact.source.startswith("constraint"):
            return True

        interaction_tokens = _normalize_tokens(interaction_signal.user_input)
        constraint_tokens = _normalize_tokens(" ".join(committed_state.constraints))
        artifact_tokens = _normalize_tokens(artifact.content)
        return bool((interaction_tokens & artifact_tokens) or (constraint_tokens & artifact_tokens))


class SimpleCognitiveCompressorAdapter(CognitiveCompressorPort):
    """規則ベースで CCS を再構成する簡易圧縮アダプタ。"""

    def __init__(self, max_retrieved_artifacts: int = 5) -> None:
        """出力 CCS に保持する Artifact 参照上限を設定する。"""
        if max_retrieved_artifacts < 1:
            raise ValueError("max_retrieved_artifacts は 1 以上である必要があります。")
        self._max_retrieved_artifacts = max_retrieved_artifacts

    def commit_next_state(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        qualified_artifacts: Sequence[Artifact],
    ) -> CompressedCognitiveState:
        """資格判定済み Artifact を反映した次の CCS を返す。"""
        turn_trace = f"turn:{interaction_signal.turn_id}:{_summarize_text(interaction_signal.user_input, 80)}"
        episodic_trace = _dedupe_and_bound(
            [*committed_state.episodic_trace[-2:], turn_trace],
            limit=3,
        )

        semantic_gist = _summarize_text(interaction_signal.user_input, 120)
        focal_entities_source = interaction_signal.focus_entities or committed_state.focal_entities
        relational_source = interaction_signal.new_facts or committed_state.relational_map
        goal_orientation = interaction_signal.active_goal or committed_state.goal_orientation
        constraints_source = interaction_signal.active_constraints or committed_state.constraints
        predictive_source = interaction_signal.expected_next_steps or committed_state.predictive_cue
        retrieved_artifacts = tuple(
            artifact.artifact_id
            for artifact in qualified_artifacts[: self._max_retrieved_artifacts]
        )
        uncertainty_signal = "低" if retrieved_artifacts else "中"

        return CompressedCognitiveState(
            episodic_trace=episodic_trace,
            semantic_gist=semantic_gist,
            focal_entities=_dedupe_and_bound(focal_entities_source, limit=8),
            relational_map=_dedupe_and_bound(relational_source, limit=8),
            goal_orientation=goal_orientation or "タスク整合性を維持する",
            constraints=_dedupe_and_bound(constraints_source, limit=8),
            predictive_cue=_dedupe_and_bound(
                predictive_source or ("次に状況を評価して応答する",),
                limit=4,
            ),
            uncertainty_signal=uncertainty_signal,
            retrieved_artifacts=retrieved_artifacts,
        )


class EchoAgentPolicyAdapter(AgentPolicyPort):
    """CCS を読み取って簡易応答を返すアダプタ。"""

    def decide(
        self,
        interaction_signal: TurnInteractionSignal,
        recent_dialogue_turns: Sequence[RecentDialogueTurn],
        committed_state: CompressedCognitiveState,
        role: str,
        tools: Sequence[str],
    ) -> AgentDecision:
        """ロールと状態要約を含む応答を生成する。"""
        tool_actions = tuple(f"use:{tool}" for tool in tools)
        history_hint = f"recent={len(recent_dialogue_turns)}"
        response = (
            f"{role} | question={_summarize_text(interaction_signal.user_input, 48)} | "
            f"goal={committed_state.goal_orientation} | "
            f"gist={committed_state.semantic_gist} | {history_hint}"
        )
        return AgentDecision(response=response, tool_actions=tool_actions)


class InMemoryEvidenceStoreAdapter(EvidenceStorePort):
    """ターン証拠を in-memory Artifact として保存するアダプタ。"""

    def __init__(self, memory: InMemoryArtifactMemory, source: str = "turn-evidence") -> None:
        """共有メモリと Artifact 生成時の source 名を受け取る。"""
        self._memory = memory
        self._source = source

    def persist_turn_evidence(
        self,
        interaction_signal: TurnInteractionSignal,
        decision: AgentDecision,
    ) -> None:
        """ターン入出力を Artifact として記録する。"""
        self._memory.append_turn_evidence_artifact(
            interaction_signal=interaction_signal,
            decision=decision,
            source=self._source,
        )


def _normalize_tokens(text: str) -> set[str]:
    """テキストを比較用トークン集合へ正規化する。"""
    ascii_tokens = {token.lower() for token in _ASCII_TOKEN_PATTERN.findall(text)}
    japanese_tokens: set[str] = set()

    for chunk in _JAPANESE_TOKEN_PATTERN.findall(text):
        normalized_chunk = chunk.strip()
        if len(normalized_chunk) < 2:
            continue
        japanese_tokens.add(normalized_chunk)
        japanese_tokens.update(_to_character_ngrams(normalized_chunk, n=2))

    return ascii_tokens | japanese_tokens


def _to_character_ngrams(text: str, *, n: int) -> set[str]:
    """文字列から固定長 n-gram 集合を生成する。"""
    if len(text) < n:
        return {text}
    return {text[index : index + n] for index in range(len(text) - n + 1)}


def _summarize_text(text: str, max_chars: int) -> str:
    """長さ上限つきでテキストを要約する。"""
    stripped = " ".join(text.strip().split())
    if len(stripped) <= max_chars:
        return stripped
    return f"{stripped[: max_chars - 3]}..."


def _dedupe_and_bound(values: Iterable[str], limit: int) -> tuple[str, ...]:
    """重複を除去しつつ先頭から上限件数だけ返す。"""
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
        if len(deduped) >= limit:
            break
    return tuple(deduped)
