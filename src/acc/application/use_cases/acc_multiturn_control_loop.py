"""ACC マルチターン制御ループのユースケース。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import (
    AgentDecision,
    RecentDialogueTurn,
    TurnInteractionSignal,
)
from acc.domain.value_objects.ccs import CompressedCognitiveState
from acc.ports.outbound.agent_policy_port import AgentPolicyPort
from acc.ports.outbound.artifact_qualification_port import ArtifactQualificationPort
from acc.ports.outbound.artifact_recall_port import ArtifactRecallPort
from acc.ports.outbound.cognitive_compressor_port import CognitiveCompressorPort
from acc.ports.outbound.evidence_store_port import EvidenceStorePort


@dataclass(frozen=True, slots=True)
class ACCTurnResult:
    """1ターン実行結果。"""

    committed_state: CompressedCognitiveState
    recalled_artifacts: tuple[Artifact, ...]
    qualified_artifacts: tuple[Artifact, ...]
    decision: AgentDecision


class ACCMultiturnControlLoop:
    """ACC の 1ターン更新と複数ターン実行を司るユースケース。"""

    def __init__(
        self,
        artifact_recall: ArtifactRecallPort,
        artifact_qualification: ArtifactQualificationPort,
        cognitive_compressor: CognitiveCompressorPort,
        agent_policy: AgentPolicyPort,
        evidence_store: EvidenceStorePort,
        *,
        recall_limit: int = 5,
        role: str = "assistant",
        tools: Sequence[str] = (),
    ) -> None:
        """依存ポートと固定パラメータを受けて初期化する。"""
        if recall_limit < 1:
            raise ValueError("recall_limit は 1 以上である必要があります。")
        self._artifact_recall = artifact_recall
        self._artifact_qualification = artifact_qualification
        self._cognitive_compressor = cognitive_compressor
        self._agent_policy = agent_policy
        self._evidence_store = evidence_store
        self._recall_limit = recall_limit
        self._role = role
        self._tools = tuple(tools)

    def run_turn(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        recent_dialogue_turns: Sequence[RecentDialogueTurn] = (),
    ) -> ACCTurnResult:
        """1ターン分の ACC 更新と意思決定を実行する。"""
        recalled_artifacts = tuple(
            self._artifact_recall.recall_candidate_artifacts(
                interaction_signal=interaction_signal,
                committed_state=committed_state,
                limit=self._recall_limit,
            )
        )[: self._recall_limit]

        qualified_artifacts = tuple(
            artifact
            for artifact in recalled_artifacts
            if self._artifact_qualification.is_decision_relevant(
                artifact=artifact,
                committed_state=committed_state,
                interaction_signal=interaction_signal,
            )
        )

        next_committed_state = self._cognitive_compressor.commit_next_state(
            interaction_signal=interaction_signal,
            committed_state=committed_state,
            qualified_artifacts=qualified_artifacts,
        )
        decision = self._agent_policy.decide(
            interaction_signal=interaction_signal,
            recent_dialogue_turns=recent_dialogue_turns,
            committed_state=next_committed_state,
            role=self._role,
            tools=self._tools,
        )
        self._evidence_store.persist_turn_evidence(
            interaction_signal=interaction_signal,
            decision=decision,
        )

        return ACCTurnResult(
            committed_state=next_committed_state,
            recalled_artifacts=recalled_artifacts,
            qualified_artifacts=qualified_artifacts,
            decision=decision,
        )

    def run_horizon(
        self,
        initial_committed_state: CompressedCognitiveState,
        interaction_signals: Sequence[TurnInteractionSignal],
    ) -> tuple[CompressedCognitiveState, tuple[ACCTurnResult, ...]]:
        """複数ターンを連続実行して最終状態を返す。"""
        committed_state = initial_committed_state
        turn_results: list[ACCTurnResult] = []

        for interaction_signal in interaction_signals:
            turn_result = self.run_turn(
                interaction_signal=interaction_signal,
                committed_state=committed_state,
            )
            committed_state = turn_result.committed_state
            turn_results.append(turn_result)

        return committed_state, tuple(turn_results)
