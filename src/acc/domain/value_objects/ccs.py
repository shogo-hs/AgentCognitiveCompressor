"""ACC の Compressed Cognitive State を表す値オブジェクト。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompressedCognitiveState:
    """ACC が各ターンで置換コミットする内部状態。"""

    episodic_trace: tuple[str, ...]
    semantic_gist: str
    focal_entities: tuple[str, ...]
    relational_map: tuple[str, ...]
    goal_orientation: str
    constraints: tuple[str, ...]
    predictive_cue: tuple[str, ...]
    uncertainty_signal: str
    retrieved_artifacts: tuple[str, ...]

    @classmethod
    def empty(cls) -> CompressedCognitiveState:
        """初期化時に使う空状態を返す。"""
        return cls(
            episodic_trace=(),
            semantic_gist="",
            focal_entities=(),
            relational_map=(),
            goal_orientation="",
            constraints=(),
            predictive_cue=(),
            uncertainty_signal="unknown",
            retrieved_artifacts=(),
        )
