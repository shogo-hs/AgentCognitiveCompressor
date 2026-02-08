from collections.abc import Mapping

import pytest

from acc.application.use_cases.live_multi_agent_evaluation import (
    LiveMultiAgentEvaluationUseCase,
)
from acc.domain.value_objects.evaluation import DriftAudit, HallucinationAudit, OutcomeScores
from acc.domain.value_objects.live_evaluation import (
    AgentTurnResponse,
    EvaluationTurnQuery,
    JudgeAgentEvaluation,
    JudgeTurnResult,
)
from acc.ports.outbound.live_evaluation_ports import AgentRunnerPort, JudgeEvaluatorPort


class ScriptedAgentRunner(AgentRunnerPort):
    """テスト用の scripted エージェントランナー。"""

    def __init__(self, name: str, *, memory_tokens_base: int) -> None:
        """エージェント名と token 計算の基準値を初期化する。"""
        self._name = name
        self._memory_tokens_base = memory_tokens_base
        self.observed_canonical_memories: list[dict[str, object]] = []

    def run_turn(
        self,
        query: EvaluationTurnQuery,
        canonical_memory: Mapping[str, object],
    ) -> AgentTurnResponse:
        """受け取った canonical memory を記録して固定応答を返す。"""
        self.observed_canonical_memories.append(dict(canonical_memory))
        return AgentTurnResponse(
            response_text=f"{self._name}: {query.user_query}",
            memory_tokens=self._memory_tokens_base + (10 * query.turn_id),
        )


class ScriptedJudgeEvaluator(JudgeEvaluatorPort):
    """テスト用の scripted judge evaluator。"""

    def __init__(self) -> None:
        """テスト観測用の履歴を初期化する。"""
        self.observed_canonical_memories: list[dict[str, object]] = []

    def evaluate_turn(
        self,
        query: EvaluationTurnQuery,
        canonical_memory: Mapping[str, object],
        agent_responses: Mapping[str, AgentTurnResponse],
    ) -> JudgeTurnResult:
        """Agent 応答を機械的に評価し次 canonical memory を返す。"""
        self.observed_canonical_memories.append(dict(canonical_memory))
        updated_canonical_memory = dict(canonical_memory)
        updated_canonical_memory["last_turn"] = query.turn_id

        evaluations_by_agent: dict[str, JudgeAgentEvaluation] = {}
        for agent_name in agent_responses:
            evaluations_by_agent[agent_name] = JudgeAgentEvaluation(
                outcome_scores=OutcomeScores(
                    relevance=8.0 if agent_name == "acc" else 6.0,
                    answer_quality=8.0 if agent_name == "acc" else 6.0,
                    instruction_following=9.0 if agent_name == "acc" else 7.0,
                    coherence=9.0 if agent_name == "acc" else 7.0,
                ),
                hallucination_audit=HallucinationAudit(
                    supported_claims=3,
                    unsupported_claims=0 if agent_name == "acc" else 1,
                ),
                drift_audit=(
                    None
                    if query.turn_id == 1
                    else DriftAudit(
                        violations=0 if agent_name == "acc" else 1,
                        omissions=0,
                        active_constraints=("no_restart", "safe_change"),
                    )
                ),
            )

        return JudgeTurnResult(
            updated_canonical_memory=updated_canonical_memory,
            evaluations_by_agent=evaluations_by_agent,
        )


class MismatchJudgeEvaluator(JudgeEvaluatorPort):
    """エージェント名不一致を作るテスト用 judge evaluator。"""

    def evaluate_turn(
        self,
        query: EvaluationTurnQuery,
        canonical_memory: Mapping[str, object],
        agent_responses: Mapping[str, AgentTurnResponse],
    ) -> JudgeTurnResult:
        """不一致エージェント名で評価結果を返す。"""
        del query, canonical_memory, agent_responses
        return JudgeTurnResult(
            updated_canonical_memory={},
            evaluations_by_agent={
                "unknown-agent": JudgeAgentEvaluation(
                    outcome_scores=OutcomeScores(
                        relevance=5.0,
                        answer_quality=5.0,
                        instruction_following=5.0,
                        coherence=5.0,
                    ),
                    hallucination_audit=HallucinationAudit(
                        supported_claims=1,
                        unsupported_claims=1,
                    ),
                    drift_audit=None,
                )
            },
        )


def test_run_episode_builds_records_and_summaries() -> None:
    baseline_runner = ScriptedAgentRunner("baseline", memory_tokens_base=100)
    acc_runner = ScriptedAgentRunner("acc", memory_tokens_base=60)
    judge = ScriptedJudgeEvaluator()
    use_case = LiveMultiAgentEvaluationUseCase(
        agent_runners={"baseline": baseline_runner, "acc": acc_runner},
        judge_evaluator=judge,
    )

    result = use_case.run_episode(
        queries=(
            EvaluationTurnQuery(turn_id=1, user_query="q1"),
            EvaluationTurnQuery(turn_id=2, user_query="q2"),
        ),
        initial_canonical_memory={"policy": "safe"},
    )

    assert set(result.turn_records_by_agent) == {"baseline", "acc"}
    assert len(result.turn_records_by_agent["baseline"]) == 2
    assert len(result.turn_records_by_agent["acc"]) == 2
    assert result.final_canonical_memory["last_turn"] == 2

    assert baseline_runner.observed_canonical_memories[0] == {"policy": "safe"}
    assert baseline_runner.observed_canonical_memories[1]["last_turn"] == 1
    assert acc_runner.observed_canonical_memories[1]["last_turn"] == 1
    assert judge.observed_canonical_memories[1]["last_turn"] == 1

    assert result.summaries_by_agent["acc"].total_turns == 2
    assert result.summaries_by_agent["baseline"].total_turns == 2
    assert (
        result.summaries_by_agent["acc"].hallucination_average
        < result.summaries_by_agent["baseline"].hallucination_average
    )


def test_run_episode_raises_when_judge_agent_name_mismatch() -> None:
    use_case = LiveMultiAgentEvaluationUseCase(
        agent_runners={"baseline": ScriptedAgentRunner("baseline", memory_tokens_base=100)},
        judge_evaluator=MismatchJudgeEvaluator(),
    )

    with pytest.raises(ValueError, match="評価対象エージェント名"):
        use_case.run_episode(queries=(EvaluationTurnQuery(turn_id=1, user_query="q1"),))
