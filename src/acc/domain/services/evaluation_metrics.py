"""ブループリント5章の評価指標を計算する。"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import mean, pstdev

from acc.domain.value_objects.evaluation import (
    AgentEvaluationSummary,
    AgentTurnEvaluationRecord,
    DriftAudit,
    HallucinationAudit,
    OutcomeScores,
)


def calculate_hallucination_turn_rate(audit: HallucinationAudit) -> float:
    """H_t = U_t / max(1, S_t + U_t) を返す。"""
    denominator = max(1, audit.supported_claims + audit.unsupported_claims)
    return audit.unsupported_claims / denominator


def calculate_drift_turn_rate(audit: DriftAudit) -> float:
    """D_t = (V_t + O_t) / max(1, |K_t|) を返す。"""
    denominator = max(1, len(audit.active_constraints))
    return (audit.violations + audit.omissions) / denominator


def summarize_agent_records(
    records: Sequence[AgentTurnEvaluationRecord],
) -> AgentEvaluationSummary:
    """単一エージェントの turn-level 評価を集計する。"""
    if not records:
        raise ValueError("records は 1 件以上必要です。")

    ordered_records = sorted(records, key=lambda record: record.turn_id)
    outcome_mean, outcome_std = _summarize_outcomes(
        [record.outcome_scores for record in ordered_records]
    )
    hallucination_turn_rates = tuple(
        calculate_hallucination_turn_rate(record.hallucination_audit) for record in ordered_records
    )
    hallucination_average = _safe_mean(hallucination_turn_rates)

    drift_turn_rates = tuple(
        calculate_drift_turn_rate(record.drift_audit)
        for record in ordered_records
        if record.turn_id >= 2 and record.drift_audit is not None
    )
    drift_average = _safe_mean(drift_turn_rates) if drift_turn_rates else None

    memory_tokens_by_turn = tuple(record.memory_tokens for record in ordered_records)
    memory_average = _safe_mean(memory_tokens_by_turn)
    memory_last_turn = memory_tokens_by_turn[-1] if memory_tokens_by_turn else None

    return AgentEvaluationSummary(
        total_turns=len(ordered_records),
        outcome_mean=outcome_mean,
        outcome_std=outcome_std,
        hallucination_turn_rates=hallucination_turn_rates,
        hallucination_average=hallucination_average,
        drift_turn_rates=drift_turn_rates,
        drift_average=drift_average,
        memory_tokens_by_turn=memory_tokens_by_turn,
        memory_average=memory_average,
        memory_last_turn=memory_last_turn,
    )


def _summarize_outcomes(scores: Sequence[OutcomeScores]) -> tuple[OutcomeScores, OutcomeScores]:
    relevance_values = [score.relevance for score in scores]
    answer_quality_values = [score.answer_quality for score in scores]
    instruction_following_values = [score.instruction_following for score in scores]
    coherence_values = [score.coherence for score in scores]

    return (
        OutcomeScores(
            relevance=_safe_mean(relevance_values),
            answer_quality=_safe_mean(answer_quality_values),
            instruction_following=_safe_mean(instruction_following_values),
            coherence=_safe_mean(coherence_values),
        ),
        OutcomeScores(
            relevance=_safe_pstdev(relevance_values),
            answer_quality=_safe_pstdev(answer_quality_values),
            instruction_following=_safe_pstdev(instruction_following_values),
            coherence=_safe_pstdev(coherence_values),
        ),
    )


def _safe_mean(values: Sequence[int | float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


def _safe_pstdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(pstdev(values))
