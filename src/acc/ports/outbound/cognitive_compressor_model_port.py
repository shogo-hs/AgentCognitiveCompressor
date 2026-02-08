"""CCM（Cognitive Compressor Model）呼び出しの契約。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import TurnInteractionSignal
from acc.domain.value_objects.ccs import CompressedCognitiveState


class CognitiveCompressorModelPort(Protocol):
    """CCS payload を生成するモデル呼び出し抽象ポート。"""

    def generate_next_state_payload(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        qualified_artifacts: Sequence[Artifact],
    ) -> Mapping[str, object]:
        """次の CCS payload を返す。"""
