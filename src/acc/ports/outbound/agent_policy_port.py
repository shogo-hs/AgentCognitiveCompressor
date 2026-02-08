"""エージェント意思決定の契約。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from acc.domain.entities.interaction import (
    AgentDecision,
    RecentDialogueTurn,
    TurnInteractionSignal,
)
from acc.domain.value_objects.ccs import CompressedCognitiveState


class AgentPolicyPort(Protocol):
    """コミット済み CCS から応答を生成する抽象ポート。"""

    def decide(
        self,
        interaction_signal: TurnInteractionSignal,
        recent_dialogue_turns: Sequence[RecentDialogueTurn],
        committed_state: CompressedCognitiveState,
        role: str,
        tools: Sequence[str],
    ) -> AgentDecision:
        """最新入力・短期対話・状態・役割・利用可能ツールを受けて結果を返す。"""
