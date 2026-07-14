"""Map gesture results to controller state."""

from __future__ import annotations

from config import Config
from controller.buttons import ButtonAction, ControllerState
from gestures.gesture_engine import GestureResult
from tracking.body_state import BodyState
from utils.filters import DeadZone, ExponentialMovingAverage


class InputMapper:
    """Combine gestures, gyro, and head tracking into controller state."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._head_yaw_ema = ExponentialMovingAverage(
            config.section("head_tracking").get("smoothing", 0.3)
        )
        self._head_pitch_ema = ExponentialMovingAverage(
            config.section("head_tracking").get("smoothing", 0.3)
        )
        self._head_deadzone = DeadZone(
            config.section("head_tracking").get("deadzone", 0.05)
        )

    def map_gestures(self, gestures: GestureResult) -> ControllerState:
        state = ControllerState()
        mov = gestures.movement
        combat = gestures.combat
        items = gestures.items
        magic = gestures.magic

        state.left_stick_x = mov.stick_x
        state.left_stick_y = mov.stick_y
        state.sprint = mov.sprint

        state.block = items.block
        state.weapon_skill = items.weapon_skill or magic.cast_spell
        state.cast_spell = magic.cast_spell

        pulses: list[ButtonAction] = []
        if mov.jump:
            pulses.append(ButtonAction.JUMP)
        if mov.dodge:
            pulses.append(ButtonAction.DODGE)
        if combat.light_attack or magic.spell_attack:
            pulses.append(ButtonAction.LIGHT_ATTACK)
        if combat.heavy_attack or combat.charged_heavy:
            pulses.append(ButtonAction.HEAVY_ATTACK)
        if items.heal_flask:
            pulses.append(ButtonAction.HEAL_FLASK)
        if magic.cast_spell and not magic.spell_attack:
            pulses.append(ButtonAction.CAST_SPELL)

        state.pulse_buttons = pulses
        return state

    def apply_head_tracking(
        self,
        body: BodyState,
        state: ControllerState,
        gyro_x: float,
        gyro_y: float,
    ) -> ControllerState:
        ht = self.config.section("head_tracking")
        if not ht.get("enabled", False) or not body.valid:
            state.right_stick_x = gyro_x
            state.right_stick_y = gyro_y
            return state

        yaw = self._head_yaw_ema.update(body.head_yaw)
        pitch = self._head_pitch_ema.update(body.head_pitch)
        hx, hy = self._head_deadzone.apply(
            yaw * ht.get("sensitivity_yaw", 0.8),
            pitch * ht.get("sensitivity_pitch", 0.6),
        )

        blend = ht.get("blend_with_gyro", 0.3)
        state.right_stick_x = gyro_x * (1 - blend) + hx * blend
        state.right_stick_y = gyro_y * (1 - blend) + hy * blend
        return state
