"""Debug overlay rendering for webcam preview."""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

try:
    import mediapipe as mp
except ImportError:
    mp = None


class DebugOverlay:
    """Render pose/hand skeletons and HUD on the camera frame."""

    def __init__(self) -> None:
        self._mp_pose = mp.solutions.pose if mp else None
        self._mp_hands = mp.solutions.hands if mp else None
        self._mp_drawing = mp.solutions.drawing_utils if mp else None
        self._mp_styles = mp.solutions.drawing_styles if mp else None
        self._fps_ema = 0.0
        self._last_time = time.perf_counter()

    def update_fps(self) -> float:
        now = time.perf_counter()
        dt = now - self._last_time
        self._last_time = now
        if dt > 0:
            instant_fps = 1.0 / dt
            self._fps_ema = 0.9 * self._fps_ema + 0.1 * instant_fps if self._fps_ema else instant_fps
        return self._fps_ema

    def draw(
        self,
        frame: np.ndarray,
        pose_landmarks: Any | None,
        left_hand_landmarks: Any | None,
        right_hand_landmarks: Any | None,
        hud: dict[str, str],
    ) -> np.ndarray:
        output = frame.copy()

        if self._mp_drawing and pose_landmarks:
            self._mp_drawing.draw_landmarks(
                output,
                pose_landmarks,
                self._mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self._mp_styles.get_default_pose_landmarks_style(),
            )

        for hand_lm in (left_hand_landmarks, right_hand_landmarks):
            if self._mp_drawing and hand_lm:
                self._mp_drawing.draw_landmarks(
                    output,
                    hand_lm,
                    self._mp_hands.HAND_CONNECTIONS,
                    self._mp_styles.get_default_hand_landmarks_style(),
                    self._mp_styles.get_default_hand_connections_style(),
                )

        fps = self.update_fps()
        lines = [
            f"FPS: {fps:.0f}",
            f"Action: {hud.get('action', 'Idle')}",
            f"Controller: {hud.get('controller', 'Unknown')}",
            f"Gyro: {hud.get('gyro', 'Unknown')}",
        ]

        if hud.get("movement"):
            lines.append(f"Move: {hud['movement']}")
        if hud.get("combat"):
            lines.append(f"Combat: {hud['combat']}")
        if hud.get("left_stick"):
            lines.append(f"L-Stick: {hud['left_stick']}")
        if hud.get("right_stick"):
            lines.append(f"R-Stick: {hud['right_stick']}")

        y = 28
        for line in lines:
            cv2.putText(
                output, line, (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 2, cv2.LINE_AA,
            )
            y += 26

        return output
