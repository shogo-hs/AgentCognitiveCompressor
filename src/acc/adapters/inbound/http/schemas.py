"""HTTP API の入出力スキーマ。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """ヘルスチェックレスポンス。"""

    status: str = "ok"


class CreateSessionResponse(BaseModel):
    """セッション作成レスポンス。"""

    session_id: str


class ChatMessageRequest(BaseModel):
    """チャットメッセージ送信リクエスト。"""

    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=10_000)


class CommittedStateResponse(BaseModel):
    """ACC がコミットした CCS 主要項目。"""

    semantic_gist: str
    goal_orientation: str
    constraints: list[str]
    predictive_cue: list[str]
    uncertainty_signal: str
    retrieved_artifacts: list[str]


class MechanismResponse(BaseModel):
    """ACC 1ターン処理の可視化情報。"""

    recalled_artifact_count: int = Field(ge=0)
    qualified_artifact_count: int = Field(ge=0)
    committed_state: CommittedStateResponse


class ChatMessageResponse(BaseModel):
    """チャットメッセージ送信レスポンス。"""

    session_id: str
    turn_id: int
    reply: str
    memory_tokens: int
    mechanism: MechanismResponse


class ErrorResponse(BaseModel):
    """API エラーレスポンス。"""

    error: str
