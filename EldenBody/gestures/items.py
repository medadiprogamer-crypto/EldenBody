"""Left hand item and utility gesture recognition."""

from __future__ import annotations

from dataclasses import dataclass

from config import Config
from tracking.body_state import BodyState
from utils.filters import CooldownManager, HoldDetector


@dataclass
class ItemOutput:
    """Item and left-hand utility actions."""

    block: bool = False
    weapon_skill: bool = False
    heal_flask: bool = False
    action_label: str = ""


class ItemRecognizer:
    """Detect block, L2, and flask heal from left hand."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cooldowns = CooldownManager()
        hold_ms = config.section("left_hand").get("flask_hold_time_ms", 500)
        self._flask_hold = HoldDetector(hold_ms)
        self._block_active = False

    def recognize(self, body: BodyState) -> ItemOutput:
        output = ItemOutput()
        hand = body.left_hand

        if not hand.detected:
            self._block_active = False
            return output

        lh_cfg = self.config.section("left_hand")

        # Open palm block
        if hand.palm_open and hand.confidence >= lh_cfg.get("block_palm_confidence", 0.7):
            output.block = True
            output.action_label = "Block (L1)"
            self._block_active = True
        else:
            self._block_active = False

        # Casting gesture: raised hand with index extended, others curled
        if hand.is_raised and hand.fingers_extended and not hand.palm_open:
            if hand.confidence >= lh_cfg.get("cast_gesture_confidence", 0.65):
                output.weapon_skill = True
                if not output.action_label:
                    output.action_label = "Weapon Skill (L2)"

        # Flask heal: hand near chest held
        if hand.near_chest:
            if self._flask_hold.update(True):
                if self.cooldowns.try_fire("heal", 1500):
                    output.heal_flask = True
                    output.action_label = "Flask Heal"
        else:
            self._flask_hold.reset()

        return output
