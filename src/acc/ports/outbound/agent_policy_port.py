"""エージェント意思決定の契約。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from acc.domain.entities.interaction import AgentDecision
from acc.domain.value_objects.ccs import CompressedCognitiveState


class AgentPolicyPort(Protocol):
    """コミット済み CCS から応答を生成する抽象ポート。"""

    def decide(
        self,
        committed_state: CompressedCognitiveState,
        role: str,
        tools: Sequence[str],
    ) -> AgentDecision:
        """役割と利用可能ツールを受けて意思決定結果を返す。"""
