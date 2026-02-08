"""評価集計で使う値オブジェクト群。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OutcomeScores:
    """5.2 の outcome 指標スコア。"""

    relevance: float
    answer_quality: float
    instruction_following: float
    coherence: float

    def __post_init__(self) -> None:
        """各スコアが 0-10 範囲にあることを検証する。"""
        _validate_score_range(self.relevance, field_name="relevance")
        _validate_score_range(self.answer_quality, field_name="answer_quality")
        _validate_score_range(self.instruction_following, field_name="instruction_following")
        _validate_score_range(self.coherence, field_name="coherence")


@dataclass(frozen=True, slots=True)
class HallucinationAudit:
    """5.3 hallucination 監査の turn-level カウント。"""

    supported_claims: int
    unsupported_claims: int

    def __post_init__(self) -> None:
        """カウントが非負整数であることを検証する。"""
        if self.supported_claims < 0:
            raise ValueError("supported_claims は 0 以上である必要があります。")
        if self.unsupported_claims < 0:
            raise ValueError("unsupported_claims は 0 以上である必要があります。")


@dataclass(frozen=True, slots=True)
class DriftAudit:
    """5.3 drift 監査の turn-level カウント。"""

    violations: int
    omissions: int
    active_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        """カウントが非負整数であることを検証する。"""
        if self.violations < 0:
            raise ValueError("violations は 0 以上である必要があります。")
        if self.omissions < 0:
            raise ValueError("omissions は 0 以上である必要があります。")


@dataclass(frozen=True, slots=True)
class AgentTurnEvaluationRecord:
    """1ターン分の評価レコード。"""

    turn_id: int
    outcome_scores: OutcomeScores
    hallucination_audit: HallucinationAudit
    drift_audit: DriftAudit | None
    memory_tokens: int

    def __post_init__(self) -> None:
        """Turn id と memory token の整合性を検証する。"""
        if self.turn_id < 1:
            raise ValueError("turn_id は 1 以上である必要があります。")
        if self.memory_tokens < 0:
            raise ValueError("memory_tokens は 0 以上である必要があります。")


@dataclass(frozen=True, slots=True)
class AgentEvaluationSummary:
    """単一エージェントの集計結果。"""

    total_turns: int
    outcome_mean: OutcomeScores
    outcome_std: OutcomeScores
    hallucination_turn_rates: tuple[float, ...]
    hallucination_average: float
    drift_turn_rates: tuple[float, ...]
    drift_average: float | None
    memory_tokens_by_turn: tuple[int, ...]
    memory_average: float
    memory_last_turn: int | None


def _validate_score_range(score: float, *, field_name: str) -> None:
    if not 0.0 <= score <= 10.0:
        raise ValueError(f"{field_name} は 0.0 から 10.0 の範囲である必要があります。")
