"""エージェント評価を集計するユースケース。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from acc.domain.services.evaluation_metrics import summarize_agent_records
from acc.domain.value_objects.evaluation import (
    AgentEvaluationSummary,
    AgentTurnEvaluationRecord,
)


class AgentJudgeEvaluationUseCase:
    """単一/複数エージェントの評価サマリーを生成する。"""

    def summarize_agent(
        self,
        turn_records: Sequence[AgentTurnEvaluationRecord],
    ) -> AgentEvaluationSummary:
        """単一エージェントの評価を集計する。"""
        return summarize_agent_records(turn_records)

    def summarize_agents(
        self,
        turn_records_by_agent: Mapping[str, Sequence[AgentTurnEvaluationRecord]],
    ) -> dict[str, AgentEvaluationSummary]:
        """複数エージェントの評価をエージェント名ごとに集計する。"""
        summaries: dict[str, AgentEvaluationSummary] = {}
        for agent_name, turn_records in turn_records_by_agent.items():
            if not agent_name:
                raise ValueError("agent_name は空にできません。")
            summaries[agent_name] = self.summarize_agent(turn_records)
        return summaries
