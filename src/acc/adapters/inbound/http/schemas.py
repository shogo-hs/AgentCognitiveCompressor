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


class ChatMessageResponse(BaseModel):
    """チャットメッセージ送信レスポンス。"""

    session_id: str
    turn_id: int
    reply: str
    memory_tokens: int


class ErrorResponse(BaseModel):
    """API エラーレスポンス。"""

    error: str
