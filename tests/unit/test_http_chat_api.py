from collections.abc import Sequence

from fastapi.testclient import TestClient

from acc.adapters.inbound.http.app import (
    _resolve_model_name,
    _resolve_non_negative_int_env,
    create_app,
)
from acc.adapters.outbound.in_memory_acc_components import (
    EchoAgentPolicyAdapter,
    SimpleCognitiveCompressorAdapter,
)
from acc.application.use_cases.chat_session import ChatSessionUseCase
from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import TurnInteractionSignal
from acc.domain.services.ccs_schema import CCSValidationError
from acc.domain.value_objects.ccs import CompressedCognitiveState
from acc.ports.outbound.cognitive_compressor_port import CognitiveCompressorPort


class FailingCognitiveCompressorAdapter(CognitiveCompressorPort):
    """CCS 検証エラーを発生させるテスト用アダプタ。"""

    def commit_next_state(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        qualified_artifacts: Sequence[Artifact],
    ) -> CompressedCognitiveState:
        del interaction_signal, committed_state, qualified_artifacts
        raise CCSValidationError("goal_orientation は空文字にできません。")


def _build_test_client() -> TestClient:
    use_case = ChatSessionUseCase(
        cognitive_compressor=SimpleCognitiveCompressorAdapter(),
        agent_policy=EchoAgentPolicyAdapter(),
        max_sessions=10,
    )
    app = create_app(chat_session_use_case=use_case)
    return TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    client = _build_test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_session_flow_works() -> None:
    client = _build_test_client()
    session_response = client.post("/api/chat/sessions")
    session_id = session_response.json()["session_id"]

    message_response = client.post(
        "/api/chat/messages",
        json={"session_id": session_id, "message": "状況をまとめて"},
    )
    payload = message_response.json()

    assert session_response.status_code == 200
    assert session_id
    assert message_response.status_code == 200
    assert payload["session_id"] == session_id
    assert payload["turn_id"] == 1
    assert payload["reply"]
    assert payload["memory_tokens"] >= 0
    assert payload["mechanism"]["recalled_artifact_count"] >= 0
    assert payload["mechanism"]["qualified_artifact_count"] >= 0
    assert isinstance(payload["mechanism"]["committed_state"]["episodic_trace"], list)
    assert payload["mechanism"]["committed_state"]["semantic_gist"]
    assert isinstance(payload["mechanism"]["committed_state"]["focal_entities"], list)
    assert isinstance(payload["mechanism"]["committed_state"]["relational_map"], list)
    assert payload["mechanism"]["committed_state"]["goal_orientation"]
    assert isinstance(payload["mechanism"]["committed_state"]["constraints"], list)
    assert isinstance(payload["mechanism"]["committed_state"]["predictive_cue"], list)
    assert payload["mechanism"]["committed_state"]["uncertainty_signal"] in {"低", "中"}
    assert isinstance(payload["mechanism"]["committed_state"]["retrieved_artifacts"], list)


def test_chat_message_with_unknown_session_returns_404() -> None:
    client = _build_test_client()

    response = client.post(
        "/api/chat/messages",
        json={"session_id": "missing-session", "message": "hello"},
    )

    assert response.status_code == 404


def test_root_serves_html() -> None:
    client = _build_test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Agent Cognitive Compressor Chat" in response.text


def test_chat_message_with_ccs_validation_error_returns_502() -> None:
    use_case = ChatSessionUseCase(
        cognitive_compressor=FailingCognitiveCompressorAdapter(),
        agent_policy=EchoAgentPolicyAdapter(),
        max_sessions=10,
    )
    client = TestClient(create_app(chat_session_use_case=use_case))
    session_id = client.post("/api/chat/sessions").json()["session_id"]

    response = client.post(
        "/api/chat/messages",
        json={"session_id": session_id, "message": "障害原因を整理して"},
    )

    assert response.status_code == 502
    assert "goal_orientation" in response.json()["detail"]


def test_resolve_model_name_prefers_role_specific_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_COMPRESSOR_MODEL", "gpt-4.1-mini-compressor")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")

    resolved = _resolve_model_name(primary_env="OPENAI_COMPRESSOR_MODEL")

    assert resolved == "gpt-4.1-mini-compressor"


def test_resolve_model_name_falls_back_to_openai_model_and_default(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_AGENT_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")
    assert _resolve_model_name(primary_env="OPENAI_AGENT_MODEL") == "gpt-4.1"

    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert _resolve_model_name(primary_env="OPENAI_AGENT_MODEL") == "gpt-4.1-mini"


def test_resolve_non_negative_int_env_uses_default_on_invalid_values(monkeypatch) -> None:
    monkeypatch.delenv("ACC_SHORT_HISTORY_TURNS", raising=False)
    assert _resolve_non_negative_int_env("ACC_SHORT_HISTORY_TURNS", default=2) == 2

    monkeypatch.setenv("ACC_SHORT_HISTORY_TURNS", "abc")
    assert _resolve_non_negative_int_env("ACC_SHORT_HISTORY_TURNS", default=2) == 2

    monkeypatch.setenv("ACC_SHORT_HISTORY_TURNS", "-1")
    assert _resolve_non_negative_int_env("ACC_SHORT_HISTORY_TURNS", default=2) == 2


def test_resolve_non_negative_int_env_accepts_zero_and_positive(monkeypatch) -> None:
    monkeypatch.setenv("ACC_SHORT_HISTORY_TURNS", "0")
    assert _resolve_non_negative_int_env("ACC_SHORT_HISTORY_TURNS", default=2) == 0

    monkeypatch.setenv("ACC_SHORT_HISTORY_TURNS", "5")
    assert _resolve_non_negative_int_env("ACC_SHORT_HISTORY_TURNS", default=2) == 5
