"""Artifact 資格判定の契約。"""

from __future__ import annotations

from typing import Protocol

from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import TurnInteractionSignal
from acc.domain.value_objects.ccs import CompressedCognitiveState


class ArtifactQualificationPort(Protocol):
    """Artifact の意思決定関連性を判定する抽象ポート。"""

    def is_decision_relevant(
        self,
        artifact: Artifact,
        committed_state: CompressedCognitiveState,
        interaction_signal: TurnInteractionSignal,
    ) -> bool:
        """Artifact がコミット対象候補として妥当かを返す。"""
