"""Artifact 想起の契約。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import TurnInteractionSignal
from acc.domain.value_objects.ccs import CompressedCognitiveState


class ArtifactRecallPort(Protocol):
    """候補 Artifact を想起する抽象ポート。"""

    def recall_candidate_artifacts(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        limit: int,
    ) -> Sequence[Artifact]:
        """候補 Artifact を上限件数つきで返す。"""
