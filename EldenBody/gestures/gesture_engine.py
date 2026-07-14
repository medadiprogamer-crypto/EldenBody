"""Central gesture recognition engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import Config
from gestures.combat import CombatOutput, CombatRecognizer
from gestures.items import ItemOutput, ItemRecognizer
from gestures.magic import MagicOutput, MagicRecognizer
from gestures.movement import MovementOutput, MovementRecognizer
from tracking.body_state import BodyState


@dataclass
class GestureResult:
    """Aggregated gesture recognition output."""

    movement: MovementOutput = field(default_factory=MovementOutput)
    combat: CombatOutput = field(default_factory=CombatOutput)
    items: ItemOutput = field(default_factory=ItemOutput)
    magic: MagicOutput = field(default_factory=MagicOutput)

    @property
    def primary_action(self) -> str:
        for label in (
            self.combat.action_label,
            self.movement.action_label,
            self.magic.action_label,
            self.items.action_label,
        ):
            if label:
                return label
        return "Idle"


class GestureEngine:
    """Orchestrate all gesture recognizers."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.movement = MovementRecognizer(config)
        self.combat = CombatRecognizer(config)
        self.items = ItemRecognizer(config)
        self.magic = MagicRecognizer(config)

    def process(self, body: BodyState) -> GestureResult:
        return GestureResult(
            movement=self.movement.recognize(body),
            combat=self.combat.recognize(body),
            items=self.items.recognize(body),
            magic=self.magic.recognize(body),
        )
