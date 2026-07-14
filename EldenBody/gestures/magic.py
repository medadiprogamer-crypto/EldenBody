"""Magic spell gesture recognition."""

from __future__ import annotations

from dataclasses import dataclass

from config import Config
from tracking.body_state import BodyState
from utils.filters import CooldownManager


@dataclass
class MagicOutput:
    """Spell casting actions."""

    cast_spell: bool = False
    spell_attack: bool = False
    action_label: str = ""


class MagicRecognizer:
    """Detect spell casting gestures from left hand."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cooldowns = CooldownManager()
        self._casting = False

    def recognize(self, body: BodyState) -> MagicOutput:
        output = MagicOutput()
        hand = body.left_hand
        magic_cfg = self.config.section("magic")

        if not hand.detected:
            self._casting = False
            return output

        raise_thresh = magic_cfg.get("raise_hand_threshold", 0.1)
        ref_y = self.config.calibration_value("left_wrist_y", 0.35)
        raised_amount = ref_y - hand.wrist[1]

        # Raise left hand to enter cast mode
        if raised_amount > raise_thresh and hand.is_raised:
            self._casting = True
            output.cast_spell = True
            output.action_label = "Cast Spell"

        # Forward hand motion while casting -> spell attack
        forward_vel = magic_cfg.get("forward_cast_velocity", 0.5)
        if self._casting and hand.velocity[2] < -forward_vel:
            if self.cooldowns.try_fire("spell_attack", magic_cfg.get("cast_cooldown_ms", 500)):
                output.spell_attack = True
                output.action_label = "Spell Attack"
                self._casting = False

        # Drop hand to cancel cast
        if raised_amount < raise_thresh * 0.3:
            self._casting = False

        return output
