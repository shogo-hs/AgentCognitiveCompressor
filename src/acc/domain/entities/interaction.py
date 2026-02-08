"""ACC 制御ループで扱うターン入出力エンティティ。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TurnInteractionSignal:
    """ACC が1ターンごとに観測する入力信号。"""

    turn_id: int
    user_input: str
    new_facts: tuple[str, ...] = ()
    focus_entities: tuple[str, ...] = ()
    active_goal: str | None = None
    active_constraints: tuple[str, ...] = ()
    expected_next_steps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """最低限の整合性を検証する。"""
        if self.turn_id < 1:
            raise ValueError("turn_id は 1 以上である必要があります。")
        if not self.user_input:
            raise ValueError("user_input は空にできません。")


@dataclass(frozen=True, slots=True)
class AgentDecision:
    """エージェントが返した応答とツール行動。"""

    response: str
    tool_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """最低限の整合性を検証する。"""
        if not self.response:
            raise ValueError("response は空にできません。")


@dataclass(frozen=True, slots=True)
class RecentDialogueTurn:
    """Policy 応答で参照する短期対話の1ターン分。"""

    turn_id: int
    user_input: str
    assistant_response: str

    def __post_init__(self) -> None:
        """最低限の整合性を検証する。"""
        if self.turn_id < 1:
            raise ValueError("turn_id は 1 以上である必要があります。")
        if not self.user_input:
            raise ValueError("user_input は空にできません。")
        if not self.assistant_response:
            raise ValueError("assistant_response は空にできません。")
