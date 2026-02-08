from datetime import UTC, datetime, timedelta

from acc.adapters.outbound.in_memory_acc_components import (
    EchoAgentPolicyAdapter,
    InMemoryArtifactMemory,
    InMemoryArtifactRecallAdapter,
    InMemoryEvidenceStoreAdapter,
    SimpleCognitiveCompressorAdapter,
    TokenOverlapQualificationAdapter,
)
from acc.application.use_cases.acc_multiturn_control_loop import ACCMultiturnControlLoop
from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import TurnInteractionSignal
from acc.domain.value_objects.ccs import CompressedCognitiveState


def _seed_artifacts() -> tuple[Artifact, ...]:
    base_time = datetime(2026, 2, 8, 10, 0, tzinfo=UTC)
    return (
        Artifact(
            artifact_id="artifact-http2",
            content="nginx http2 rollout triggered 502 spikes",
            source="incident-log",
            created_at=base_time,
        ),
        Artifact(
            artifact_id="artifact-constraint",
            content="no_restart nginx during business hours",
            source="constraint-note",
            created_at=base_time + timedelta(minutes=1),
        ),
        Artifact(
            artifact_id="artifact-unrelated",
            content="marketing campaign assets",
            source="chat-log",
            created_at=base_time + timedelta(minutes=2),
        ),
    )


def test_run_turn_applies_recall_limit_and_persists_evidence() -> None:
    memory = InMemoryArtifactMemory(seed_artifacts=_seed_artifacts())
    loop = ACCMultiturnControlLoop(
        artifact_recall=InMemoryArtifactRecallAdapter(memory),
        artifact_qualification=TokenOverlapQualificationAdapter(),
        cognitive_compressor=SimpleCognitiveCompressorAdapter(max_retrieved_artifacts=3),
        agent_policy=EchoAgentPolicyAdapter(),
        evidence_store=InMemoryEvidenceStoreAdapter(memory),
        recall_limit=2,
        role="triage-agent",
        tools=("log_search",),
    )

    interaction_signal = TurnInteractionSignal(
        turn_id=1,
        user_input="Need a safe mitigation for nginx 502 after enabling http2",
        active_goal="reduce_502_rate",
        active_constraints=("no_restart", "safe_change"),
        focus_entities=("nginx", "http2", "error_502"),
        expected_next_steps=("check_upstream_latency",),
    )
    initial_state = CompressedCognitiveState.empty()

    result = loop.run_turn(interaction_signal=interaction_signal, committed_state=initial_state)

    assert len(result.recalled_artifacts) <= 2
    assert result.committed_state != initial_state
    assert result.committed_state.goal_orientation == "reduce_502_rate"
    assert result.committed_state.retrieved_artifacts == tuple(
        artifact.artifact_id for artifact in result.qualified_artifacts
    )
    assert len(memory.turn_records) == 1
    assert any(artifact.source == "turn-evidence" for artifact in memory.list_artifacts())


def test_run_horizon_replaces_committed_state_every_turn() -> None:
    memory = InMemoryArtifactMemory(seed_artifacts=_seed_artifacts())
    loop = ACCMultiturnControlLoop(
        artifact_recall=InMemoryArtifactRecallAdapter(memory),
        artifact_qualification=TokenOverlapQualificationAdapter(),
        cognitive_compressor=SimpleCognitiveCompressorAdapter(max_retrieved_artifacts=5),
        agent_policy=EchoAgentPolicyAdapter(),
        evidence_store=InMemoryEvidenceStoreAdapter(memory),
        recall_limit=3,
    )

    signals = (
        TurnInteractionSignal(
            turn_id=1,
            user_input="Investigate nginx 502 errors after http2 change",
            active_goal="stabilize_service",
            active_constraints=("no_restart",),
            expected_next_steps=("collect_upstream_metrics",),
        ),
        TurnInteractionSignal(
            turn_id=2,
            user_input="Now propose next checks without restart",
            active_goal="preserve_availability",
            active_constraints=("no_restart", "no_speculation"),
            expected_next_steps=("summarize_mitigation",),
        ),
    )

    initial_state = CompressedCognitiveState.empty()
    final_state, turn_results = loop.run_horizon(
        initial_committed_state=initial_state,
        interaction_signals=signals,
    )

    assert len(turn_results) == 2
    assert all(len(turn_result.recalled_artifacts) <= 3 for turn_result in turn_results)
    assert turn_results[0].committed_state != turn_results[1].committed_state
    assert final_state == turn_results[-1].committed_state
    assert len(memory.turn_records) == 2
    assert len(memory.list_artifacts()) == len(_seed_artifacts()) + 2
