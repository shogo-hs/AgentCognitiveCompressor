"""CCS スキーマの検証と正規化を提供する。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from acc.domain.value_objects.ccs import CompressedCognitiveState

REQUIRED_FIELDS: tuple[str, ...] = (
    "episodic_trace",
    "semantic_gist",
    "focal_entities",
    "relational_map",
    "goal_orientation",
    "constraints",
    "predictive_cue",
    "uncertainty_signal",
    "retrieved_artifacts",
)

DEFAULT_LIST_LIMITS: Mapping[str, int] = {
    "episodic_trace": 3,
    "focal_entities": 8,
    "relational_map": 8,
    "constraints": 8,
    "predictive_cue": 4,
    "retrieved_artifacts": 5,
}


class CCSValidationError(ValueError):
    """CCS スキーマ違反を表す例外。"""


def parse_and_validate_ccs_payload(
    payload: Mapping[str, object],
    *,
    list_limits: Mapping[str, int] | None = None,
) -> CompressedCognitiveState:
    """モデル出力 payload を検証して CCS へ変換する。"""
    _validate_required_fields(payload)
    merged_limits = dict(DEFAULT_LIST_LIMITS)
    if list_limits:
        merged_limits.update(list_limits)

    episodic_trace = _normalize_string_sequence(
        payload["episodic_trace"],
        field_name="episodic_trace",
        limit=merged_limits["episodic_trace"],
    )
    semantic_gist = _normalize_non_empty_string(
        payload["semantic_gist"], field_name="semantic_gist"
    )
    focal_entities = _normalize_string_sequence(
        payload["focal_entities"],
        field_name="focal_entities",
        limit=merged_limits["focal_entities"],
    )
    relational_map = _normalize_string_sequence(
        payload["relational_map"],
        field_name="relational_map",
        limit=merged_limits["relational_map"],
    )
    goal_orientation = _normalize_non_empty_string(
        payload["goal_orientation"],
        field_name="goal_orientation",
    )
    constraints = _normalize_string_sequence(
        payload["constraints"],
        field_name="constraints",
        limit=merged_limits["constraints"],
    )
    predictive_cue = _normalize_string_sequence(
        payload["predictive_cue"],
        field_name="predictive_cue",
        limit=merged_limits["predictive_cue"],
    )
    uncertainty_signal = _normalize_non_empty_string(
        payload["uncertainty_signal"],
        field_name="uncertainty_signal",
    )
    retrieved_artifacts = _normalize_string_sequence(
        payload["retrieved_artifacts"],
        field_name="retrieved_artifacts",
        limit=merged_limits["retrieved_artifacts"],
    )

    return CompressedCognitiveState(
        episodic_trace=episodic_trace,
        semantic_gist=semantic_gist,
        focal_entities=focal_entities,
        relational_map=relational_map,
        goal_orientation=goal_orientation,
        constraints=constraints,
        predictive_cue=predictive_cue,
        uncertainty_signal=uncertainty_signal,
        retrieved_artifacts=retrieved_artifacts,
    )


def _validate_required_fields(payload: Mapping[str, object]) -> None:
    missing_fields = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise CCSValidationError(f"CCS payload に必須フィールドが不足しています: {joined}")


def _normalize_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise CCSValidationError(f"{field_name} は文字列である必要があります。")
    normalized = value.strip()
    if not normalized:
        raise CCSValidationError(f"{field_name} は空文字にできません。")
    return normalized


def _normalize_string_sequence(value: object, *, field_name: str, limit: int) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise CCSValidationError(f"{field_name} は文字列配列である必要があります。")
    if limit < 1:
        raise CCSValidationError(f"{field_name} の上限値は 1 以上である必要があります。")

    normalized_values: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise CCSValidationError(f"{field_name}[{index}] は文字列である必要があります。")
        candidate = item.strip()
        if not candidate:
            raise CCSValidationError(f"{field_name}[{index}] は空文字にできません。")
        normalized_values.append(candidate)
        if len(normalized_values) >= limit:
            break

    return tuple(normalized_values)
