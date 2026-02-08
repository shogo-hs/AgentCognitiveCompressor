"""ライブ評価オーケストレーションで使う値オブジェクト。"""

from __future__ import annotations

from dataclasses import dataclass

from acc.domain.value_objects.evaluation import (
    AgentEvaluationSummary,
    AgentTurnEvaluationRecord,
    DriftAudit,
    HallucinationAudit,
    OutcomeScores,
)


@dataclass(frozen=True, slots=True)
class EvaluationTurnQuery:
    """1ターン分の評価クエリ。"""

    turn_id: int
    user_query: str

    def __post_init__(self) -> None:
        """Turn 定義の最小整合性を検証する。"""
        if self.turn_id < 1:
            raise ValueError("turn_id は 1 以上である必要があります。")
        if not self.user_query.strip():
            raise ValueError("user_query は空にできません。")


@dataclass(frozen=True, slots=True)
class AgentTurnResponse:
    """1ターンでエージェントが返した応答。"""

    response_text: str
    memory_tokens: int

    def __post_init__(self) -> None:
        """応答と memory token の最小整合性を検証する。"""
        if not self.response_text.strip():
            raise ValueError("response_text は空にできません。")
        if self.memory_tokens < 0:
            raise ValueError("memory_tokens は 0 以上である必要があります。")


@dataclass(frozen=True, slots=True)
class JudgeAgentEvaluation:
    """judge がエージェントごとに返す評価結果。"""

    outcome_scores: OutcomeScores
    hallucination_audit: HallucinationAudit
    drift_audit: DriftAudit | None


@dataclass(frozen=True, slots=True)
class JudgeTurnResult:
    """judge の1ターン評価結果。"""

    updated_canonical_memory: dict[str, object]
    evaluations_by_agent: dict[str, JudgeAgentEvaluation]


@dataclass(frozen=True, slots=True)
class LiveEvaluationEpisodeResult:
    """ライブ評価 episode の最終結果。"""

    turn_records_by_agent: dict[str, tuple[AgentTurnEvaluationRecord, ...]]
    summaries_by_agent: dict[str, AgentEvaluationSummary]
    final_canonical_memory: dict[str, object]
