"""ライブ評価で使う agent / judge の契約。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from acc.domain.value_objects.live_evaluation import (
    AgentTurnResponse,
    EvaluationTurnQuery,
    JudgeTurnResult,
)


class AgentRunnerPort(Protocol):
    """1ターンのエージェント応答を実行する抽象ポート。"""

    def run_turn(
        self,
        query: EvaluationTurnQuery,
        canonical_memory: Mapping[str, object],
    ) -> AgentTurnResponse:
        """クエリと canonical memory から応答を返す。"""


class JudgeEvaluatorPort(Protocol):
    """複数エージェント応答を評価する judge 抽象ポート。"""

    def evaluate_turn(
        self,
        query: EvaluationTurnQuery,
        canonical_memory: Mapping[str, object],
        agent_responses: Mapping[str, AgentTurnResponse],
    ) -> JudgeTurnResult:
        """Judge 評価結果と更新 canonical memory を返す。"""
