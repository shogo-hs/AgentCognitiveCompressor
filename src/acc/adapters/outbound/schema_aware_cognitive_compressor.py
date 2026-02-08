"""CCS スキーマ準拠で状態コミットする圧縮アダプタ。"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from acc.domain.entities.artifact import Artifact
from acc.domain.entities.interaction import TurnInteractionSignal
from acc.domain.services.ccs_schema import CCSValidationError, parse_and_validate_ccs_payload
from acc.domain.value_objects.ccs import CompressedCognitiveState
from acc.ports.outbound.cognitive_compressor_model_port import CognitiveCompressorModelPort
from acc.ports.outbound.cognitive_compressor_port import CognitiveCompressorPort

_LOG = logging.getLogger(__name__)
_DEFAULT_GOAL = "ユーザー意図の確認と課題解決を継続する"
_UNCERTAINTY_MARKERS: tuple[str, ...] = (
    "不明",
    "わから",
    "未確認",
    "確認できない",
    "推測",
    "かもしれ",
    "不確実",
    "?",
)


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
        qualified_artifacts_tuple = tuple(qualified_artifacts)
        payload = self._model.generate_next_state_payload(
            interaction_signal=interaction_signal,
            committed_state=committed_state,
            qualified_artifacts=qualified_artifacts_tuple,
        )
        repaired_payload, applied_fields = _apply_semantic_fallback(
            payload=payload,
            interaction_signal=interaction_signal,
            committed_state=committed_state,
            qualified_artifacts=qualified_artifacts_tuple,
        )
        if applied_fields:
            _LOG.info(
                "CCS semantic fallback applied: turn_id=%s fields=%s",
                interaction_signal.turn_id,
                ",".join(applied_fields),
            )
        try:
            return parse_and_validate_ccs_payload(repaired_payload, list_limits=self._list_limits)
        except CCSValidationError:
            # 補正対象外の不正は明示的に失敗させる。
            raise


def _apply_semantic_fallback(
    *,
    payload: Mapping[str, object],
    interaction_signal: TurnInteractionSignal,
    committed_state: CompressedCognitiveState,
    qualified_artifacts: Sequence[Artifact],
) -> tuple[dict[str, object], tuple[str, ...]]:
    """空NGフィールドに対して文脈準拠の最小フォールバックを適用する。"""
    repaired: dict[str, object] = dict(payload)
    applied_fields: list[str] = []

    if _as_non_empty_text(repaired.get("goal_orientation")) is None:
        repaired["goal_orientation"] = _fallback_goal_orientation(
            interaction_signal=interaction_signal,
            committed_state=committed_state,
        )
        applied_fields.append("goal_orientation")

    if _as_non_empty_text(repaired.get("semantic_gist")) is None:
        repaired["semantic_gist"] = _fallback_semantic_gist(
            interaction_signal=interaction_signal,
            committed_state=committed_state,
            qualified_artifacts=qualified_artifacts,
            goal_orientation=_as_non_empty_text(repaired.get("goal_orientation")) or _DEFAULT_GOAL,
        )
        applied_fields.append("semantic_gist")

    if _as_non_empty_text(repaired.get("uncertainty_signal")) is None:
        repaired["uncertainty_signal"] = _fallback_uncertainty_signal(
            interaction_signal=interaction_signal,
            committed_state=committed_state,
            qualified_artifacts=qualified_artifacts,
        )
        applied_fields.append("uncertainty_signal")

    return repaired, tuple(applied_fields)


def _fallback_goal_orientation(
    *,
    interaction_signal: TurnInteractionSignal,
    committed_state: CompressedCognitiveState,
) -> str:
    """goal_orientation の意味準拠フォールバックを返す。"""
    active_goal = _as_non_empty_text(interaction_signal.active_goal)
    if active_goal is not None:
        return active_goal

    previous_goal = _as_non_empty_text(committed_state.goal_orientation)
    if previous_goal is not None:
        return previous_goal

    base = _summarize_text(interaction_signal.user_input, max_chars=48)
    primary_constraint = _primary_constraint(
        interaction_signal=interaction_signal,
        committed_state=committed_state,
    )
    if primary_constraint is not None:
        return f"{base}への対応を進めつつ、{primary_constraint}を順守する"
    return f"{base}への対応方針を明確化する"


def _fallback_semantic_gist(
    *,
    interaction_signal: TurnInteractionSignal,
    committed_state: CompressedCognitiveState,
    qualified_artifacts: Sequence[Artifact],
    goal_orientation: str,
) -> str:
    """semantic_gist の意味準拠フォールバックを返す。"""
    segments = [f"入力:{_summarize_text(interaction_signal.user_input, max_chars=72)}"]
    segments.append(f"目的:{goal_orientation}")

    primary_constraint = _primary_constraint(
        interaction_signal=interaction_signal,
        committed_state=committed_state,
    )
    if primary_constraint is not None:
        segments.append(f"制約:{primary_constraint}")

    first_artifact_hint = _first_artifact_hint(qualified_artifacts)
    if first_artifact_hint is not None:
        segments.append(f"根拠:{first_artifact_hint}")

    return _summarize_text(" / ".join(segments), max_chars=180)


def _fallback_uncertainty_signal(
    *,
    interaction_signal: TurnInteractionSignal,
    committed_state: CompressedCognitiveState,
    qualified_artifacts: Sequence[Artifact],
) -> str:
    """uncertainty_signal の意味準拠フォールバックを返す。"""
    user_input = interaction_signal.user_input
    if any(marker in user_input for marker in _UNCERTAINTY_MARKERS):
        return "高"

    qualified_count = len(qualified_artifacts)
    if qualified_count == 0:
        return "高"

    has_relational_context = bool(committed_state.relational_map)
    if qualified_count >= 2 and has_relational_context:
        return "低"
    if qualified_count >= 1:
        return "中"
    return "高"


def _primary_constraint(
    *,
    interaction_signal: TurnInteractionSignal,
    committed_state: CompressedCognitiveState,
) -> str | None:
    """現ターンで優先する制約を返す。"""
    constraints = interaction_signal.active_constraints or committed_state.constraints
    if not constraints:
        return None
    return _as_non_empty_text(constraints[0])


def _first_artifact_hint(qualified_artifacts: Sequence[Artifact]) -> str | None:
    """想起証拠の先頭を短く要約して返す。"""
    if not qualified_artifacts:
        return None
    artifact = qualified_artifacts[0]
    content = _as_non_empty_text(artifact.content)
    if content is None:
        return artifact.artifact_id
    return f"{artifact.source}:{_summarize_text(content, max_chars=56)}"


def _as_non_empty_text(value: object) -> str | None:
    """空白除去後に非空の文字列を返す。"""
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.strip().split())
    if not normalized:
        return None
    return normalized


def _summarize_text(text: str, *, max_chars: int) -> str:
    """長すぎる文を末尾省略して返す。"""
    normalized = " ".join(text.strip().split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3]}..."
