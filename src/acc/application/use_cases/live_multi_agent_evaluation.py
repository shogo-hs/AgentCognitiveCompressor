"""複数エージェントのライブ評価を実行するユースケース。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from acc.application.use_cases.agent_judge_evaluation import AgentJudgeEvaluationUseCase
from acc.domain.value_objects.evaluation import AgentTurnEvaluationRecord
from acc.domain.value_objects.live_evaluation import (
    EvaluationTurnQuery,
    LiveEvaluationEpisodeResult,
)
from acc.ports.outbound.live_evaluation_ports import AgentRunnerPort, JudgeEvaluatorPort


class LiveMultiAgentEvaluationUseCase:
    """judge 駆動の multi-agent 評価 episode を実行する。"""

    def __init__(
        self,
        *,
        agent_runners: Mapping[str, AgentRunnerPort],
        judge_evaluator: JudgeEvaluatorPort,
        summary_use_case: AgentJudgeEvaluationUseCase | None = None,
    ) -> None:
        """依存ポートと集計ユースケースを初期化する。"""
        if not agent_runners:
            raise ValueError("agent_runners は 1 件以上必要です。")
        if any(not name.strip() for name in agent_runners):
            raise ValueError("agent_runners のキー名は空にできません。")

        self._agent_runners = dict(agent_runners)
        self._judge_evaluator = judge_evaluator
        self._summary_use_case = summary_use_case or AgentJudgeEvaluationUseCase()

    def run_episode(
        self,
        queries: Sequence[EvaluationTurnQuery],
        *,
        initial_canonical_memory: Mapping[str, object] | None = None,
    ) -> LiveEvaluationEpisodeResult:
        """Turn query 列を順に処理し、episode 結果を返す。"""
        if not queries:
            raise ValueError("queries は 1 件以上必要です。")

        canonical_memory: dict[str, object] = dict(initial_canonical_memory or {})
        records_by_agent: dict[str, list[AgentTurnEvaluationRecord]] = {
            agent_name: [] for agent_name in self._agent_runners
        }

        for query in queries:
            agent_responses = {
                agent_name: runner.run_turn(
                    query=query,
                    canonical_memory=dict(canonical_memory),
                )
                for agent_name, runner in self._agent_runners.items()
            }

            judge_result = self._judge_evaluator.evaluate_turn(
                query=query,
                canonical_memory=dict(canonical_memory),
                agent_responses=agent_responses,
            )
            self._validate_judge_result(
                expected_agent_names=set(self._agent_runners),
                actual_agent_names=set(judge_result.evaluations_by_agent),
            )

            canonical_memory = dict(judge_result.updated_canonical_memory)
            for agent_name, agent_evaluation in judge_result.evaluations_by_agent.items():
                records_by_agent[agent_name].append(
                    AgentTurnEvaluationRecord(
                        turn_id=query.turn_id,
                        outcome_scores=agent_evaluation.outcome_scores,
                        hallucination_audit=agent_evaluation.hallucination_audit,
                        drift_audit=agent_evaluation.drift_audit,
                        memory_tokens=agent_responses[agent_name].memory_tokens,
                    )
                )

        frozen_records_by_agent = {
            agent_name: tuple(records) for agent_name, records in records_by_agent.items()
        }
        summaries = self._summary_use_case.summarize_agents(frozen_records_by_agent)

        return LiveEvaluationEpisodeResult(
            turn_records_by_agent=frozen_records_by_agent,
            summaries_by_agent=summaries,
            final_canonical_memory=canonical_memory,
        )

    def _validate_judge_result(
        self,
        *,
        expected_agent_names: set[str],
        actual_agent_names: set[str],
    ) -> None:
        if expected_agent_names != actual_agent_names:
            missing = sorted(expected_agent_names - actual_agent_names)
            unexpected = sorted(actual_agent_names - expected_agent_names)
            raise ValueError(
                "judge の評価対象エージェント名が一致しません。"
                f" missing={missing}, unexpected={unexpected}"
            )
