"""外部証拠として扱う Artifact エンティティ。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Artifact:
    """想起対象となる外部証拠。"""

    artifact_id: str
    content: str
    source: str
    created_at: datetime

    def __post_init__(self) -> None:
        """最低限の整合性を検証する。"""
        if not self.artifact_id:
            raise ValueError("artifact_id は空にできません。")
        if not self.content:
            raise ValueError("content は空にできません。")
        if not self.source:
            raise ValueError("source は空にできません。")
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=UTC))
