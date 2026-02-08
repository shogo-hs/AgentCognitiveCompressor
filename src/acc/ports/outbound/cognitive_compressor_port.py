"""CCS コミットの契約。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import TurnInteractionSignal
from acc.domain.value_objects.ccs import CompressedCognitiveState


class CognitiveCompressorPort(Protocol):
    """次の CCS を構築する抽象ポート。"""

    def commit_next_state(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        qualified_artifacts: Sequence[Artifact],
    ) -> CompressedCognitiveState:
        """資格判定済み Artifact を使って次状態を返す。"""
