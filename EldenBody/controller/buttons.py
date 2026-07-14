"""Xbox controller button identifiers and input state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class ButtonAction(Enum):
    """Transient button press actions."""

    JUMP = auto()
    DODGE = auto()
    LIGHT_ATTACK = auto()
    HEAVY_ATTACK = auto()
    BLOCK = auto()
    WEAPON_SKILL = auto()
    HEAL_FLASK = auto()
    CAST_SPELL = auto()
    SPELL_ATTACK = auto()


@dataclass
class ControllerState:
    """Complete virtual controller state for one update cycle."""

    left_stick_x: float = 0.0
    left_stick_y: float = 0.0
    right_stick_x: float = 0.0
    right_stick_y: float = 0.0
    sprint: bool = False

    # Held buttons
    block: bool = False
    weapon_skill: bool = False
    cast_spell: bool = False

    # Pulse buttons (fire once)
    pulse_buttons: list[ButtonAction] | None = None

    def __post_init__(self) -> None:
        if self.pulse_buttons is None:
            self.pulse_buttons = []
