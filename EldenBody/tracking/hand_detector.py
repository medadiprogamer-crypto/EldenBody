"""MediaPipe Hands detection and sword gesture metrics."""

from __future__ import annotations

import math
import time
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from config import Config
from tracking.body_state import BodyState, HandState
from utils.filters import ConfidenceChecker, VelocityTracker, VectorEMA


class HandDetector:
    """Detect hands and compute combat/cast gesture metrics."""

    WRIST = 0
    THUMB_TIP = 4
    INDEX_TIP = 8
    MIDDLE_TIP = 12
    RING_TIP = 16
    PINKY_TIP = 20
    INDEX_MCP = 5
    MIDDLE_MCP = 9

    def __init__(self, config: Config) -> None:
        self.config = config
        self._hands = mp.solutions.hands.Hands(
            model_complexity=1,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        alpha = config.section("filtering").get("hand_smoothing", 0.35)
        self._left_tracker = VelocityTracker(smoothing=alpha)
        self._right_tracker = VelocityTracker(smoothing=alpha)
        self._left_pos_ema = VectorEMA(alpha, 3)
        self._right_pos_ema = VectorEMA(alpha, 3)
        self._angle_history: dict[str, list[float]] = {"left": [], "right": []}

    def process(self, frame: np.ndarray, body_state: BodyState) -> BodyState:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)
        timestamp = body_state.timestamp or time.perf_counter()

        body_state.left_hand = HandState()
        body_state.right_hand = HandState()

        if not results.multi_hand_landmarks:
            return body_state

        handedness = results.multi_handedness or []
        for idx, hand_lm in enumerate(results.multi_hand_landmarks):
            label = "Right"
            if idx < len(handedness):
                label = handedness[idx].classification[0].label

            # MediaPipe labels are mirrored for selfie camera
            is_right = label == "Left"
            hand_state = self._extract_hand_state(hand_lm, is_right, timestamp, body_state)
            if is_right:
                body_state.right_hand = hand_state
            else:
                body_state.left_hand = hand_state

        return body_state

    def _extract_hand_state(
        self,
        hand_lm: Any,
        is_right: bool,
        timestamp: float,
        body_state: BodyState,
    ) -> HandState:
        lm = hand_lm.landmark
        state = HandState(detected=True, landmarks=hand_lm)

        wrist = (lm[self.WRIST].x, lm[self.WRIST].y, lm[self.WRIST].z)
        index_tip = (lm[self.INDEX_TIP].x, lm[self.INDEX_TIP].y, lm[self.INDEX_TIP].z)
        middle_tip = (lm[self.MIDDLE_TIP].x, lm[self.MIDDLE_TIP].y, lm[self.MIDDLE_TIP].z)

        palm_center = (
            (wrist[0] + lm[self.MIDDLE_MCP].x) / 2,
            (wrist[1] + lm[self.MIDDLE_MCP].y) / 2,
            (wrist[2] + lm[self.MIDDLE_MCP].z) / 2,
        )

        tracker = self._right_tracker if is_right else self._left_tracker
        pos_ema = self._right_pos_ema if is_right else self._left_pos_ema
        smoothed = pos_ema.update(wrist)
        motion = tracker.update(smoothed, timestamp)

        state.wrist = wrist
        state.index_tip = index_tip
        state.middle_tip = middle_tip
        state.palm_center = palm_center
        state.velocity = motion["velocity"]
        state.acceleration = motion["acceleration"]
        state.speed = motion["speed"]

        state.swing_angle = self._compute_swing_angle(wrist, index_tip)
        state.swing_direction = self._classify_direction(state.velocity, state.swing_angle)

        state.fingers_extended = self._fingers_extended(lm)
        state.palm_open = self._palm_open(lm)
        state.confidence = ConfidenceChecker.average([1.0] * len(lm), 0.5)

        side = "right" if is_right else "left"
        ref_y = self.config.calibration_value(f"{side}_wrist_y", 0.35)
        state.is_raised = wrist[1] < ref_y - 0.05

        chest_y = body_state.shoulder_center[1] + 0.08
        chest_x = body_state.shoulder_center[0]
        dist = math.sqrt((wrist[0] - chest_x) ** 2 + (wrist[1] - chest_y) ** 2)
        flask_dist = self.config.section("left_hand").get("flask_chest_distance", 0.15)
        state.near_chest = dist < flask_dist and not is_right

        return state

    def _compute_swing_angle(
        self,
        wrist: tuple[float, float, float],
        tip: tuple[float, float, float],
    ) -> float:
        dx = tip[0] - wrist[0]
        dy = tip[1] - wrist[1]
        return math.degrees(math.atan2(dy, dx))

    def _classify_direction(
        self,
        velocity: tuple[float, float, float],
        angle: float,
    ) -> str:
        vx, vy, vz = velocity
        speed = (vx * vx + vy * vy + vz * vz) ** 0.5
        if speed < 0.3:
            return "none"
        if abs(vx) > abs(vy) and abs(vx) > abs(vz):
            return "horizontal"
        if vy > abs(vx) and vy > abs(vz):
            return "downward"
        if vy < -abs(vx) and vy < -abs(vz):
            return "upward"
        if abs(vz) > abs(vx) and abs(vz) > abs(vy):
            return "thrust"
        if 20 < angle < 70:
            return "diagonal"
        return "forward"

    def _fingers_extended(self, lm: list) -> bool:
        tips = [self.INDEX_TIP, self.MIDDLE_TIP, self.RING_TIP, self.PINKY_TIP]
        mcps = [self.INDEX_MCP, self.MIDDLE_MCP, 13, 17]
        extended = 0
        for tip, mcp in zip(tips, mcps):
            if lm[tip].y < lm[mcp].y:
                extended += 1
        return extended >= 3

    def _palm_open(self, lm: list) -> bool:
        tips = [self.INDEX_TIP, self.MIDDLE_TIP, self.RING_TIP, self.PINKY_TIP]
        wrist = lm[self.WRIST]
        spread = 0
        for tip_idx in tips:
            dist = math.sqrt(
                (lm[tip_idx].x - wrist.x) ** 2 + (lm[tip_idx].y - wrist.y) ** 2
            )
            spread += dist
        avg_spread = spread / len(tips)
        return avg_spread > 0.12 and self._fingers_extended(lm)

    def close(self) -> None:
        self._hands.close()
