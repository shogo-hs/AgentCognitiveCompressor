from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from acc.adapters.outbound.in_memory_acc_components import (
    EchoAgentPolicyAdapter,
    InMemoryArtifactMemory,
    InMemoryArtifactRecallAdapter,
    InMemoryEvidenceStoreAdapter,
    TokenOverlapQualificationAdapter,
)
from acc.adapters.outbound.schema_aware_cognitive_compressor import (
    SchemaAwareCognitiveCompressorAdapter,
)
from acc.application.use_cases.acc_multiturn_control_loop import ACCMultiturnControlLoop
from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import TurnInteractionSignal
from acc.domain.services.ccs_schema import CCSValidationError, parse_and_validate_ccs_payload
from acc.domain.value_objects.ccs import CompressedCognitiveState
from acc.ports.outbound.cognitive_compressor_model_port import CognitiveCompressorModelPort


def _valid_payload() -> dict[str, object]:
    return {
        "episodic_trace": [" observed(nginx_502) ", " constraint(no_restart) "],
        "semantic_gist": " mitigate 502 safely ",
        "focal_entities": ["nginx", "upstream", "http2"],
        "relational_map": ["timing(after_http2_enable)"],
        "goal_orientation": "reduce_502_rate",
        "constraints": ["no_restart", "safe_change"],
        "predictive_cue": ["check_upstream_latency"],
        "uncertainty_signal": "medium",
        "retrieved_artifacts": ["a1", "a2", "a3", "a4"],
    }


def test_parse_and_validate_payload_normalizes_and_applies_limits() -> None:
    payload = _valid_payload()

    parsed = parse_and_validate_ccs_payload(
        payload,
        list_limits={
            "episodic_trace": 1,
            "retrieved_artifacts": 2,
        },
    )

    assert parsed.episodic_trace == ("observed(nginx_502)",)
    assert parsed.semantic_gist == "mitigate 502 safely"
    assert parsed.retrieved_artifacts == ("a1", "a2")


def test_parse_and_validate_payload_rejects_missing_field() -> None:
    payload = _valid_payload()
    payload.pop("constraints")

    with pytest.raises(CCSValidationError, match="constraints"):
        parse_and_validate_ccs_payload(payload)


def test_parse_and_validate_payload_rejects_invalid_field_type() -> None:
    payload = _valid_payload()
    payload["constraints"] = "no_restart"

    with pytest.raises(CCSValidationError, match="constraints"):
        parse_and_validate_ccs_payload(payload)


class DummyCompressorModel(CognitiveCompressorModelPort):
    """テスト用の固定 payload 返却モデル。"""

    def __init__(self, payload: dict[str, object]) -> None:
        """返却 payload を受け取り初期化する。"""
        self._payload = payload
        self.call_count = 0

    def generate_next_state_payload(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        qualified_artifacts: Sequence[Artifact],
    ) -> dict[str, object]:
        del interaction_signal, committed_state, qualified_artifacts
        self.call_count += 1
        return self._payload


def test_schema_aware_compressor_fills_empty_non_nullable_fields() -> None:
    payload = _valid_payload()
    payload["semantic_gist"] = "   "
    payload["goal_orientation"] = ""
    payload["uncertainty_signal"] = ""
    model = DummyCompressorModel(payload)
    compressor = SchemaAwareCognitiveCompressorAdapter(model=model)
    previous_state = CompressedCognitiveState(
        episodic_trace=("turn:0:準備",),
        semantic_gist="準備中",
        focal_entities=("nginx",),
        relational_map=("after_http2_enable",),
        goal_orientation="障害影響を最小化する",
        constraints=("no_restart",),
        predictive_cue=("次に状況を評価して応答する",),
        uncertainty_signal="中",
        retrieved_artifacts=(),
    )
    interaction_signal = TurnInteractionSignal(
        turn_id=1,
        user_input="Nginx 502 を抑えたい",
        active_constraints=("no_restart",),
    )

    next_state = compressor.commit_next_state(
        interaction_signal=interaction_signal,
        committed_state=previous_state,
        qualified_artifacts=(),
    )

    assert next_state.goal_orientation == "障害影響を最小化する"
    assert "入力:" in next_state.semantic_gist
    assert "目的:" in next_state.semantic_gist
    assert next_state.uncertainty_signal == "高"


def test_schema_aware_compressor_prefers_active_goal_as_fallback() -> None:
    payload = _valid_payload()
    payload["goal_orientation"] = "   "
    model = DummyCompressorModel(payload)
    compressor = SchemaAwareCognitiveCompressorAdapter(model=model)
    interaction_signal = TurnInteractionSignal(
        turn_id=1,
        user_input="次の手順を整理して",
        active_goal="復旧計画を更新する",
    )

    next_state = compressor.commit_next_state(
        interaction_signal=interaction_signal,
        committed_state=CompressedCognitiveState.empty(),
        qualified_artifacts=(),
    )

    assert next_state.goal_orientation == "復旧計画を更新する"


def test_schema_aware_compressor_runs_in_acc_loop() -> None:
    seed_artifact = Artifact(
        artifact_id="seed-1",
        content="nginx 502 after http2 enable",
        source="incident-log",
        created_at=datetime(2026, 2, 8, 12, 0, tzinfo=UTC),
    )
    memory = InMemoryArtifactMemory(seed_artifacts=(seed_artifact,))
    model = DummyCompressorModel(_valid_payload())
    compressor = SchemaAwareCognitiveCompressorAdapter(
        model=model,
        list_limits={"retrieved_artifacts": 2},
    )
    loop = ACCMultiturnControlLoop(
        artifact_recall=InMemoryArtifactRecallAdapter(memory),
        artifact_qualification=TokenOverlapQualificationAdapter(),
        cognitive_compressor=compressor,
        agent_policy=EchoAgentPolicyAdapter(),
        evidence_store=InMemoryEvidenceStoreAdapter(memory),
        recall_limit=3,
    )

    interaction_signal = TurnInteractionSignal(
        turn_id=1,
        user_input="Need mitigation for nginx 502 after enabling http2",
        active_goal="reduce_502_rate",
        active_constraints=("no_restart",),
    )
    result = loop.run_turn(
        interaction_signal=interaction_signal,
        committed_state=CompressedCognitiveState.empty(),
    )

    assert model.call_count == 1
    assert result.committed_state.semantic_gist == "mitigate 502 safely"
    assert result.committed_state.retrieved_artifacts == ("a1", "a2")
    assert len(memory.turn_records) == 1
