"""ターン証拠の永続化契約。"""

from __future__ import annotations

from typing import Protocol

from acc.domain.entities.interaction import AgentDecision, TurnInteractionSignal


class EvidenceStorePort(Protocol):
    """ターン入出力を将来想起用に保存する抽象ポート。"""

    def persist_turn_evidence(
        self,
        interaction_signal: TurnInteractionSignal,
        decision: AgentDecision,
    ) -> None:
        """ターン証拠を保存する。"""
