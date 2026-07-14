"""Right-hand sword combat gesture recognition."""

from __future__ import annotations

import time
from dataclasses import dataclass

from config import Config
from tracking.body_state import BodyState
from utils.filters import CooldownManager, HoldDetector


@dataclass
class CombatOutput:
    """Combat button outputs from sword gestures."""

    light_attack: bool = False
    heavy_attack: bool = False
    charged_heavy: bool = False
    action_label: str = ""


class CombatRecognizer:
    """Detect sword swings from right hand motion."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cooldowns = CooldownManager()
        self._backward_hold = HoldDetector(
            config.combat_value("charged_hold_time_ms", 400)
        )
        self._was_backward = False
        self._backward_start_time: float | None = None

    def recognize(self, body: BodyState) -> CombatOutput:
        output = CombatOutput()
        hand = body.right_hand

        if not hand.detected or hand.confidence < self.config.combat_value("confidence_threshold", 0.6):
            self._was_backward = False
            self._backward_hold.reset()
            return output

        if not self.cooldowns.ready("attack", self.config.combat_value("attack_cooldown_ms", 350)):
            return output

        speed = hand.speed
        direction = hand.swing_direction
        light_vel = self.config.combat_value("light_attack_velocity", 0.8)
        heavy_vel = self.config.combat_value("heavy_attack_velocity", 0.4)
        charged_vel = self.config.combat_value("charged_velocity", 1.2)
        thrust_vel = self.config.combat_value("thrust_velocity", 0.7)

        # Detect backward hold for charged attack
        is_backward = hand.velocity[2] < -0.2 or (
            hand.swing_angle > 120 and speed < 0.3
        )
        if is_backward:
            if self._backward_start_time is None:
                self._backward_start_time = time.perf_counter()
            self._was_backward = True
        else:
            if self._was_backward and speed >= charged_vel:
                if self.cooldowns.try_fire("attack", self.config.combat_value("attack_cooldown_ms", 350)):
                    output.charged_heavy = True
                    output.heavy_attack = True
                    output.action_label = "Charged Heavy Attack"
                    self._was_backward = False
                    self._backward_start_time = None
                    return output
            self._was_backward = False
            self._backward_start_time = None

        # Fast horizontal swing -> light attack
        if direction == "horizontal" and speed >= light_vel:
            if self.cooldowns.try_fire("attack", self.config.combat_value("attack_cooldown_ms", 350)):
                output.light_attack = True
                output.action_label = "Light Attack (R1)"
                return output

        # Upward swing
        if direction == "upward" and speed >= heavy_vel:
            if self.cooldowns.try_fire("attack", self.config.combat_value("attack_cooldown_ms", 350)):
                output.heavy_attack = True
                output.action_label = "Upper Slash"
                return output

        # Diagonal downward
        diag_min = self.config.combat_value("diagonal_angle_min", 30.0)
        if direction == "diagonal" and speed >= heavy_vel and hand.swing_angle > diag_min:
            if self.cooldowns.try_fire("attack", self.config.combat_value("attack_cooldown_ms", 350)):
                output.heavy_attack = True
                output.action_label = "Diagonal Heavy"
                return output

        if direction == "downward" and speed >= heavy_vel:
            if self.cooldowns.try_fire("attack", self.config.combat_value("attack_cooldown_ms", 350)):
                output.heavy_attack = True
                output.action_label = "Downward Heavy"
                return output

        # Thrust
        if direction == "thrust" and speed >= thrust_vel:
            if self.cooldowns.try_fire("attack", self.config.combat_value("attack_cooldown_ms", 350)):
                output.light_attack = True
                output.action_label = "Thrust Attack"
                return output

        # Slow powerful swing -> heavy
        if speed >= heavy_vel and speed < light_vel and direction in ("forward", "horizontal"):
            if self.cooldowns.try_fire("attack", self.config.combat_value("attack_cooldown_ms", 350)):
                output.heavy_attack = True
                output.action_label = "Heavy Attack (R2)"
                return output

        return output
