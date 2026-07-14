"""Virtual Xbox 360 controller output via ViGEm."""

from __future__ import annotations

import threading
import time

import vgamepad as vg

from controller.buttons import ButtonAction, ControllerState

# Stick value range for vgamepad
STICK_MAX = 32767


class XboxController:
    """Thread-safe virtual Xbox controller."""

    PULSE_DURATION_MS = 50

    def __init__(self) -> None:
        self._pad = vg.VX360Gamepad()
        self._lock = threading.Lock()
        self._connected = True
        self._active_pulses: dict[ButtonAction, float] = {}
        self._last_state = ControllerState()

    @property
    def connected(self) -> bool:
        return self._connected

    def _float_to_stick(self, value: float) -> int:
        clamped = max(-1.0, min(1.0, value))
        return int(clamped * STICK_MAX)

    def _set_button(self, button: int, pressed: bool) -> None:
        if pressed:
            self._pad.press_button(button=button)
        else:
            self._pad.release_button(button=button)

    def _update_pulses(self) -> None:
        now = time.perf_counter() * 1000.0
        expired = [action for action, expiry in self._active_pulses.items() if now >= expiry]
        for action in expired:
            del self._active_pulses[action]

    def _is_pulsed(self, action: ButtonAction) -> bool:
        return action in self._active_pulses

    def _register_pulses(self, actions: list[ButtonAction]) -> None:
        now = time.perf_counter() * 1000.0
        for action in actions:
            self._active_pulses[action] = now + self.PULSE_DURATION_MS

    def update(self, state: ControllerState) -> None:
        with self._lock:
            try:
                self._update_pulses()

                if state.pulse_buttons:
                    self._register_pulses(state.pulse_buttons)

                # Left stick
                self._pad.left_joystick(
                    x_value=self._float_to_stick(state.left_stick_x),
                    y_value=self._float_to_stick(-state.left_stick_y),
                )

                # Right stick (camera)
                self._pad.right_joystick(
                    x_value=self._float_to_stick(state.right_stick_x),
                    y_value=self._float_to_stick(-state.right_stick_y),
                )

                # Sprint = L3
                self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB, state.sprint)

                # Held buttons
                self._set_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER, state.block)
                self._set_button(
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
                    state.weapon_skill or self._is_pulsed(ButtonAction.LIGHT_ATTACK),
                )

                # Pulse buttons (Elden Ring Xbox layout)
                self._set_button(
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
                    self._is_pulsed(ButtonAction.JUMP),
                )
                self._set_button(
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
                    self._is_pulsed(ButtonAction.DODGE),
                )
                self._set_button(
                    vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
                    self._is_pulsed(ButtonAction.HEAL_FLASK),
                )

                # L2 = LT (weapon skill / aim), R2 = RT (heavy attack)
                heavy = self._is_pulsed(ButtonAction.HEAVY_ATTACK)
                self._pad.left_trigger(value=255 if state.weapon_skill or state.cast_spell else 0)
                self._pad.right_trigger(value=255 if heavy else 0)

                self._pad.update()
                self._last_state = state
                self._connected = True
            except Exception:
                self._connected = False

    def reset(self) -> None:
        with self._lock:
            try:
                self._pad.reset()
                self._pad.update()
                self._active_pulses.clear()
            except Exception:
                self._connected = False

    def release(self) -> None:
        self.reset()
