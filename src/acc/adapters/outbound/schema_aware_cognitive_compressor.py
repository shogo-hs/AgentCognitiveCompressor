"""CCS スキーマ準拠で状態コミットする圧縮アダプタ。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import TurnInteractionSignal
from acc.domain.services.ccs_schema import parse_and_validate_ccs_payload
from acc.domain.value_objects.ccs import CompressedCognitiveState
from acc.ports.outbound.cognitive_compressor_model_port import CognitiveCompressorModelPort
from acc.ports.outbound.cognitive_compressor_port import CognitiveCompressorPort


class SchemaAwareCognitiveCompressorAdapter(CognitiveCompressorPort):
    """CCM payload をスキーマ検証して CCS に変換する。"""

    def __init__(
        self,
        model: CognitiveCompressorModelPort,
        *,
        list_limits: Mapping[str, int] | None = None,
    ) -> None:
        """モデルポートと任意の配列上限設定を受け取る。"""
        self._model = model
        self._list_limits = dict(list_limits) if list_limits else None

    def commit_next_state(
        self,
        interaction_signal: TurnInteractionSignal,
        committed_state: CompressedCognitiveState,
        qualified_artifacts: Sequence[Artifact],
    ) -> CompressedCognitiveState:
        """モデル出力 payload を検証して次状態を返す。"""
        payload = self._model.generate_next_state_payload(
            interaction_signal=interaction_signal,
            committed_state=committed_state,
            qualified_artifacts=tuple(qualified_artifacts),
        )
        return parse_and_validate_ccs_payload(payload, list_limits=self._list_limits)
