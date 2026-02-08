from fastapi.testclient import TestClient

from acc.adapters.inbound.http.app import create_app
from acc.adapters.outbound.in_memory_acc_components import (
    EchoAgentPolicyAdapter,
    SimpleCognitiveCompressorAdapter,
)
from acc.application.use_cases.chat_session import ChatSessionUseCase


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
    assert payload["mechanism"]["committed_state"]["semantic_gist"]
    assert payload["mechanism"]["committed_state"]["goal_orientation"]
    assert isinstance(payload["mechanism"]["committed_state"]["constraints"], list)
    assert isinstance(payload["mechanism"]["committed_state"]["predictive_cue"], list)
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
