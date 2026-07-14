"""MediaPipe Pose detection and body metric extraction."""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from config import Config
from tracking.body_state import BodyState
from utils.filters import ExponentialMovingAverage, VectorEMA


class PoseDetector:
    """Detect body pose and compute movement metrics."""

    # MediaPipe Pose landmark indices
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self, config: Config) -> None:
        self.config = config
        self._pose = mp.solutions.pose.Pose(
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        alpha = config.section("filtering").get("pose_smoothing", 0.4)
        self._hip_ema = VectorEMA(alpha, 2)
        self._shoulder_ema = VectorEMA(alpha, 2)
        self._torso_ema = ExponentialMovingAverage(alpha)
        self._knee_history: deque[tuple[float, float, float]] = deque(maxlen=30)
        self._hip_history: deque[tuple[float, float]] = deque(maxlen=10)
        self._prev_torso_angle = 0.0
        self._frame_id = 0

    def process(self, frame: np.ndarray) -> BodyState:
        self._frame_id += 1
        timestamp = time.perf_counter()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)

        state = BodyState(timestamp=timestamp, frame_id=self._frame_id)
        if not results.pose_landmarks:
            return state

        lm = results.pose_landmarks.landmark
        state.pose_landmarks = results.pose_landmarks
        state.pose_world_landmarks = results.pose_world_landmarks

        visibilities = [lm[i].visibility for i in range(len(lm))]
        state.pose_confidence = sum(visibilities) / len(visibilities)
        state.valid = state.pose_confidence > 0.5

        nose = (lm[self.NOSE].x, lm[self.NOSE].y)
        left_shoulder = (lm[self.LEFT_SHOULDER].x, lm[self.LEFT_SHOULDER].y)
        right_shoulder = (lm[self.RIGHT_SHOULDER].x, lm[self.RIGHT_SHOULDER].y)
        left_hip = (lm[self.LEFT_HIP].x, lm[self.LEFT_HIP].y)
        right_hip = (lm[self.RIGHT_HIP].x, lm[self.RIGHT_HIP].y)

        hip_center = ((left_hip[0] + right_hip[0]) / 2, (left_hip[1] + right_hip[1]) / 2)
        shoulder_center = (
            (left_shoulder[0] + right_shoulder[0]) / 2,
            (left_shoulder[1] + right_shoulder[1]) / 2,
        )

        hip_center = self._hip_ema.update(hip_center)
        shoulder_center = self._shoulder_ema.update(shoulder_center)

        state.hip_center = hip_center
        state.shoulder_center = shoulder_center
        state.nose = nose

        dx = shoulder_center[0] - hip_center[0]
        dy = shoulder_center[1] - hip_center[1]
        torso_angle = math.degrees(math.atan2(dx, -dy + 1e-6))
        state.torso_angle = self._torso_ema.update(torso_angle)

        neutral = self.config.calibration_value("torso_angle_neutral", 0.0)
        angle_delta = state.torso_angle - neutral
        state.lean_forward = max(0.0, angle_delta)
        state.lean_backward = max(0.0, -angle_delta)

        neutral_hip_x = self.config.calibration_value("neutral_hip_x", 0.5)
        state.strafe_offset = hip_center[0] - neutral_hip_x

        # Head orientation from nose offset relative to shoulders
        shoulder_width = abs(right_shoulder[0] - left_shoulder[0]) + 1e-6
        state.head_yaw = (nose[0] - shoulder_center[0]) / shoulder_width
        state.head_pitch = (nose[1] - shoulder_center[1]) / shoulder_width

        # Knee and ankle tracking
        state.left_knee_y = lm[self.LEFT_KNEE].y
        state.right_knee_y = lm[self.RIGHT_KNEE].y
        state.left_ankle_y = lm[self.LEFT_ANKLE].y
        state.right_ankle_y = lm[self.RIGHT_ANKLE].y

        neutral_hip_y = self.config.calibration_value("neutral_hip_y", 0.5)
        knee_lift_l = neutral_hip_y - state.left_knee_y
        knee_lift_r = neutral_hip_y - state.right_knee_y
        state.knee_lift_avg = (knee_lift_l + knee_lift_r) / 2

        self._knee_history.append((timestamp, state.left_knee_y, state.right_knee_y))
        self._hip_history.append(hip_center)

        state.leg_oscillation, state.leg_frequency = self._compute_leg_motion()
        state.is_walking, state.is_sprinting = self._detect_walk_run(state)
        state.hip_delta_y = self._compute_hip_delta()
        state.is_jumping = self._detect_jump(state)
        state.is_dodging = self._detect_dodge(state)

        self._prev_torso_angle = state.torso_angle
        return state

    def _compute_leg_motion(self) -> tuple[float, float]:
        if len(self._knee_history) < 5:
            return 0.0, 0.0

        left_vals = [h[1] for h in self._knee_history]
        right_vals = [h[2] for h in self._knee_history]
        amplitude = (max(left_vals) - min(left_vals) + max(right_vals) - min(right_vals)) / 2

        timestamps = [h[0] for h in self._knee_history]
        dt = timestamps[-1] - timestamps[0]
        if dt <= 0:
            return amplitude, 0.0

        # Count zero-crossings for frequency estimate
        diffs = [(left_vals[i] - left_vals[i - 1]) for i in range(1, len(left_vals))]
        crossings = sum(1 for i in range(1, len(diffs)) if diffs[i] * diffs[i - 1] < 0)
        frequency = crossings / (2 * dt)
        return amplitude, frequency

    def _detect_walk_run(self, state: BodyState) -> tuple[bool, bool]:
        walk_amp = self.config.calibration_value("walk_knee_amplitude", 0.02)
        run_amp = self.config.calibration_value("run_knee_amplitude", 0.06)
        walk_freq = self.config.calibration_value("walk_frequency", 1.5)
        run_freq = self.config.calibration_value("run_frequency", 3.0)

        amp = state.leg_oscillation
        freq = state.leg_frequency
        walk_threshold = self.config.movement_value("walk_speed_threshold", 0.015)

        is_walking = amp >= max(walk_amp * 0.5, walk_threshold) and freq >= walk_freq * 0.5
        is_sprinting = amp >= run_amp * 0.7 and freq >= run_freq * 0.7
        return is_walking, is_sprinting

    def _compute_hip_delta(self) -> float:
        if len(self._hip_history) < 3:
            return 0.0
        neutral = self.config.calibration_value("neutral_hip_y", 0.5)
        current_y = self._hip_history[-1][1]
        return neutral - current_y

    def _detect_jump(self, state: BodyState) -> bool:
        threshold = self.config.calibration_value("jump_hip_delta", 0.04)
        return state.hip_delta_y > threshold and state.knee_lift_avg > threshold * 0.5

    def _detect_dodge(self, state: BodyState) -> bool:
        dodge_angle = self.config.calibration_value("dodge_bend_angle", 25.0)
        angle_change = state.torso_angle - self._prev_torso_angle
        return state.lean_forward > dodge_angle and angle_change > 8.0

    def close(self) -> None:
        self._pose.close()
