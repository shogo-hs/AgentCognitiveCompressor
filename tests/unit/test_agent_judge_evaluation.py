import pytest

from acc.application.use_cases.agent_judge_evaluation import AgentJudgeEvaluationUseCase
from acc.domain.services.evaluation_metrics import (
    calculate_drift_turn_rate,
    calculate_hallucination_turn_rate,
    summarize_agent_records,
)
from acc.domain.value_objects.evaluation import (
    AgentTurnEvaluationRecord,
    DriftAudit,
    HallucinationAudit,
    OutcomeScores,
)


def _build_records_for_acc() -> tuple[AgentTurnEvaluationRecord, ...]:
    return (
        AgentTurnEvaluationRecord(
            turn_id=1,
            outcome_scores=OutcomeScores(
                relevance=8.0,
                answer_quality=7.0,
                instruction_following=9.0,
                coherence=8.0,
            ),
            hallucination_audit=HallucinationAudit(
                supported_claims=3,
                unsupported_claims=1,
            ),
            drift_audit=None,
            memory_tokens=100,
        ),
        AgentTurnEvaluationRecord(
            turn_id=2,
            outcome_scores=OutcomeScores(
                relevance=9.0,
                answer_quality=8.0,
                instruction_following=9.0,
                coherence=9.0,
            ),
            hallucination_audit=HallucinationAudit(
                supported_claims=4,
                unsupported_claims=0,
            ),
            drift_audit=DriftAudit(
                violations=1,
                omissions=1,
                active_constraints=("no_restart", "safe_change", "format", "policy"),
            ),
            memory_tokens=80,
        ),
        AgentTurnEvaluationRecord(
            turn_id=3,
            outcome_scores=OutcomeScores(
                relevance=7.0,
                answer_quality=8.0,
                instruction_following=8.0,
                coherence=7.0,
            ),
            hallucination_audit=HallucinationAudit(
                supported_claims=1,
                unsupported_claims=1,
            ),
            drift_audit=DriftAudit(
                violations=0,
                omissions=1,
                active_constraints=("no_restart", "safe_change"),
            ),
            memory_tokens=60,
        ),
    )


def test_summarize_agent_records_matches_formula_definitions() -> None:
    summary = summarize_agent_records(_build_records_for_acc())

    assert summary.total_turns == 3
    assert summary.hallucination_turn_rates == pytest.approx((0.25, 0.0, 0.5))
    assert summary.hallucination_average == pytest.approx(0.25)
    assert summary.drift_turn_rates == pytest.approx((0.5, 0.5))
    assert summary.drift_average == pytest.approx(0.5)
    assert summary.memory_tokens_by_turn == (100, 80, 60)
    assert summary.memory_average == pytest.approx(80.0)
    assert summary.memory_last_turn == 60

    assert summary.outcome_mean.relevance == pytest.approx(8.0)
    assert summary.outcome_mean.answer_quality == pytest.approx(7.6666666667)
    assert summary.outcome_mean.instruction_following == pytest.approx(8.6666666667)
    assert summary.outcome_mean.coherence == pytest.approx(8.0)

    assert summary.outcome_std.relevance == pytest.approx(0.8164965809)
    assert summary.outcome_std.answer_quality == pytest.approx(0.4714045208)
    assert summary.outcome_std.instruction_following == pytest.approx(0.4714045208)
    assert summary.outcome_std.coherence == pytest.approx(0.8164965809)


def test_turn_rate_helpers_handle_zero_division_guards() -> None:
    hallucination_rate = calculate_hallucination_turn_rate(
        HallucinationAudit(
            supported_claims=0,
            unsupported_claims=0,
        )
    )
    drift_rate = calculate_drift_turn_rate(
        DriftAudit(
            violations=1,
            omissions=0,
            active_constraints=(),
        )
    )

    assert hallucination_rate == pytest.approx(0.0)
    assert drift_rate == pytest.approx(1.0)


def test_use_case_summarizes_multiple_agents_independently() -> None:
    use_case = AgentJudgeEvaluationUseCase()
    summaries = use_case.summarize_agents(
        {
            "baseline": (
                AgentTurnEvaluationRecord(
                    turn_id=1,
                    outcome_scores=OutcomeScores(
                        relevance=4.0,
                        answer_quality=5.0,
                        instruction_following=4.0,
                        coherence=4.0,
                    ),
                    hallucination_audit=HallucinationAudit(
                        supported_claims=1,
                        unsupported_claims=1,
                    ),
                    drift_audit=None,
                    memory_tokens=120,
                ),
            ),
            "acc": _build_records_for_acc(),
        }
    )

    assert set(summaries) == {"baseline", "acc"}
    assert summaries["baseline"].total_turns == 1
    assert summaries["baseline"].memory_last_turn == 120
    assert summaries["baseline"].hallucination_average == pytest.approx(0.5)

    assert summaries["acc"].total_turns == 3
    assert summaries["acc"].memory_last_turn == 60
    assert summaries["acc"].hallucination_average == pytest.approx(0.25)
