"""FastAPI ベースの ACC チャット API。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from acc.adapters.inbound.http.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    CommittedStateResponse,
    CreateSessionResponse,
    ErrorResponse,
    HealthResponse,
    MechanismResponse,
)
from acc.adapters.outbound.openai_chat_adapters import (
    OpenAIAgentPolicyAdapter,
    OpenAICognitiveCompressorModelAdapter,
    OpenAIConfigurationError,
    OpenAIRequestError,
    OpenAIResponseFormatError,
)
from acc.adapters.outbound.schema_aware_cognitive_compressor import (
    SchemaAwareCognitiveCompressorAdapter,
)
from acc.application.use_cases.chat_session import (
    ChatSessionNotFoundError,
    ChatSessionUseCase,
)

_BASE_DIR = Path(__file__).resolve().parent
_STATIC_HTML = _BASE_DIR / "static" / "index.html"


def create_app(*, chat_session_use_case: ChatSessionUseCase | None = None) -> FastAPI:
    """ACC チャット API アプリを構築する。"""
    _load_runtime_env()
    use_case = chat_session_use_case or _build_default_chat_use_case()

    app = FastAPI(
        title="ACC Chat API",
        version="0.1.0",
    )
    app.state.chat_session_use_case = use_case
    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:
    api = APIRouter(prefix="/api")

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @api.post(
        "/chat/sessions",
        response_model=CreateSessionResponse,
    )
    def create_session() -> CreateSessionResponse:
        use_case: ChatSessionUseCase = app.state.chat_session_use_case
        session_id = use_case.create_session()
        return CreateSessionResponse(session_id=session_id)

    @api.post(
        "/chat/messages",
        response_model=ChatMessageResponse,
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    def post_message(request: ChatMessageRequest) -> ChatMessageResponse:
        use_case: ChatSessionUseCase = app.state.chat_session_use_case
        try:
            reply = use_case.send_message(
                session_id=request.session_id,
                message=request.message,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except ChatSessionNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except OpenAIConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except OpenAIRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        except OpenAIResponseFormatError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        return ChatMessageResponse(
            session_id=reply.session_id,
            turn_id=reply.turn_id,
            reply=reply.reply,
            memory_tokens=reply.memory_tokens,
            mechanism=MechanismResponse(
                recalled_artifact_count=reply.mechanism.recalled_artifact_count,
                qualified_artifact_count=reply.mechanism.qualified_artifact_count,
                committed_state=CommittedStateResponse(
                    episodic_trace=list(reply.mechanism.committed_state.episodic_trace),
                    semantic_gist=reply.mechanism.committed_state.semantic_gist,
                    focal_entities=list(reply.mechanism.committed_state.focal_entities),
                    relational_map=list(reply.mechanism.committed_state.relational_map),
                    goal_orientation=reply.mechanism.committed_state.goal_orientation,
                    constraints=list(reply.mechanism.committed_state.constraints),
                    predictive_cue=list(reply.mechanism.committed_state.predictive_cue),
                    uncertainty_signal=reply.mechanism.committed_state.uncertainty_signal,
                    retrieved_artifacts=list(reply.mechanism.committed_state.retrieved_artifacts),
                ),
            ),
        )

    @app.get("/", response_class=FileResponse)
    def serve_index() -> FileResponse:
        if not _STATIC_HTML.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="UI ファイルがありません。"
            )
        return FileResponse(path=_STATIC_HTML)

    app.include_router(api)


def _build_default_chat_use_case() -> ChatSessionUseCase:
    compressor_model = OpenAICognitiveCompressorModelAdapter(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0.1,
        max_output_tokens=900,
    )
    compressor = SchemaAwareCognitiveCompressorAdapter(model=compressor_model)
    policy = OpenAIAgentPolicyAdapter(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0.2,
        max_output_tokens=1000,
    )
    return ChatSessionUseCase(
        cognitive_compressor=compressor,
        agent_policy=policy,
        role="acc-assistant",
        recall_limit=5,
        max_sessions=200,
    )


def _load_runtime_env() -> None:
    app_env = os.getenv("APP_ENV", "development")
    env_file = Path(f".env.{app_env}")
    if env_file.exists():
        load_dotenv(env_file, override=False)
    else:
        load_dotenv(override=False)
