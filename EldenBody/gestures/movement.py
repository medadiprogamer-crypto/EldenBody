"""Movement gesture recognition for locomotion."""

from __future__ import annotations

from dataclasses import dataclass

from config import Config
from tracking.body_state import BodyState
from utils.filters import CooldownManager, DeadZone


@dataclass
class MovementOutput:
    """Virtual left stick and movement button state."""

    stick_x: float = 0.0
    stick_y: float = 0.0
    sprint: bool = False
    jump: bool = False
    dodge: bool = False
    action_label: str = "Idle"


class MovementRecognizer:
    """Map body pose metrics to movement controls."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.cooldowns = CooldownManager()
        self.deadzone = DeadZone(config.movement_value("stick_deadzone", 0.08))

    def recognize(self, body: BodyState) -> MovementOutput:
        output = MovementOutput()
        if not body.valid:
            output.action_label = "No Pose"
            return output

        cal = self.config.section("calibration")
        mov = self.config.section("movement")

        stick_y = 0.0
        stick_x = 0.0

        # Forward movement from walking/running in place
        if body.is_walking or body.is_sprinting:
            intensity = min(1.0, body.leg_oscillation / max(cal.get("walk_knee_amplitude", 0.02), 0.01))
            if body.is_sprinting:
                intensity = min(1.0, intensity * mov.get("sprint_amplitude_multiplier", 1.8))
                output.sprint = True
                output.action_label = "Sprint"
            else:
                output.action_label = "Walk"
            stick_y = intensity * mov.get("stick_sensitivity", 1.0)

        # Backward from lean
        lean_back_thresh = abs(cal.get("lean_back_angle", -15.0))
        if body.lean_backward > lean_back_thresh * 0.3:
            stick_y = -min(1.0, body.lean_backward / 30.0) * mov.get("lean_sensitivity", 1.2)
            output.action_label = "Lean Back"

        # Strafe from hip offset
        strafe_thresh = cal.get("strafe_threshold", 0.03)
        if abs(body.strafe_offset) > strafe_thresh:
            stick_x = max(-1.0, min(1.0, body.strafe_offset / 0.1))
            stick_x *= mov.get("strafe_sensitivity", 1.5)
            if output.action_label == "Idle":
                output.action_label = "Strafe"

        stick_x, stick_y = self.deadzone.apply(stick_x, stick_y)
        output.stick_x = stick_x
        output.stick_y = stick_y

        # Jump
        if body.is_jumping and self.cooldowns.try_fire(
            "jump", self.config.movement_value("jump_cooldown_ms", 600)
        ):
            output.jump = True
            output.action_label = "Jump"

        # Dodge roll
        if body.is_dodging and self.cooldowns.try_fire(
            "dodge", self.config.movement_value("dodge_cooldown_ms", 800)
        ):
            output.dodge = True
            output.action_label = "Dodge Roll"

        return output
