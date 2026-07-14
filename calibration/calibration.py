"""Interactive calibration wizard for body control."""

from __future__ import annotations

import time
from typing import Callable

import cv2
import numpy as np

from config import Config
from tracking.body_state import BodyState
from tracking.hand_detector import HandDetector
from tracking.pose_detector import PoseDetector


class CalibrationStep:
    """Single calibration step definition."""

    def __init__(
        self,
        name: str,
        instruction: str,
        duration_s: float,
        collector: Callable[[BodyState, dict], None],
    ) -> None:
        self.name = name
        self.instruction = instruction
        self.duration_s = duration_s
        self.collector = collector


class CalibrationWizard:
    """Guided first-launch calibration sequence."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._samples: dict[str, list] = {}
        self._pose = PoseDetector(config)
        self._hands = HandDetector(config)

    def _add_sample(self, key: str, value: float) -> None:
        self._samples.setdefault(key, []).append(value)

    def _avg(self, key: str, default: float = 0.0) -> float:
        vals = self._samples.get(key, [])
        return sum(vals) / len(vals) if vals else default

    def _build_steps(self) -> list[CalibrationStep]:
        return [
            CalibrationStep(
                "neutral",
                "Stand normally facing the camera. Hold still.",
                3.0,
                lambda b, _: (
                    self._add_sample("neutral_hip_y", b.hip_center[1]),
                    self._add_sample("neutral_hip_x", b.hip_center[0]),
                    self._add_sample("neutral_shoulder_y", b.shoulder_center[1]),
                    self._add_sample("torso_angle_neutral", b.torso_angle),
                ),
            ),
            CalibrationStep(
                "right_hand",
                "Raise your RIGHT hand (sword hand) and hold.",
                2.5,
                lambda b, _: self._add_sample("right_wrist_y", b.right_hand.wrist[1])
                if b.right_hand.detected else None,
            ),
            CalibrationStep(
                "left_hand",
                "Raise your LEFT hand and hold.",
                2.5,
                lambda b, _: self._add_sample("left_wrist_y", b.left_hand.wrist[1])
                if b.left_hand.detected else None,
            ),
            CalibrationStep(
                "sword_hold",
                "Hold your sword (tube) in ready position.",
                2.5,
                lambda b, _: self._add_sample("sword_hold_angle", b.right_hand.swing_angle)
                if b.right_hand.detected else None,
            ),
            CalibrationStep(
                "walk",
                "Walk in place slowly for 4 seconds.",
                4.0,
                lambda b, _: (
                    self._add_sample("walk_knee_amplitude", b.leg_oscillation),
                    self._add_sample("walk_frequency", b.leg_frequency),
                ),
            ),
            CalibrationStep(
                "run",
                "Run in place with high knees for 4 seconds.",
                4.0,
                lambda b, _: (
                    self._add_sample("run_knee_amplitude", b.leg_oscillation),
                    self._add_sample("run_frequency", b.leg_frequency),
                ),
            ),
            CalibrationStep(
                "dodge",
                "Do a quick forward bend (dodge motion) 3 times.",
                5.0,
                lambda b, _: self._add_sample("dodge_bend_angle", b.lean_forward)
                if b.lean_forward > 10 else None,
            ),
            CalibrationStep(
                "jump",
                "Do 3 small jumps.",
                5.0,
                lambda b, _: self._add_sample("jump_hip_delta", b.hip_delta_y)
                if b.is_jumping else None,
            ),
        ]

    def run(self, camera_index: int = 0) -> bool:
        # Using default backend (MediaFoundation on Windows)
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print("[Calibration] ERROR: Could not open webcam.")
            return False

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.get("camera_width", 640))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.get("camera_height", 480))

        steps = self._build_steps()
        print("\n=== EldenBody Calibration ===\n")

        for i, step in enumerate(steps, 1):
            print(f"Step {i}/{len(steps)}: {step.instruction}")
            start = time.perf_counter()
            countdown_shown = False

            while time.perf_counter() - start < step.duration_s:
                ret, frame = cap.read()
                if not ret:
                    continue

                body = self._pose.process(frame)
                body = self._hands.process(frame, body)
                step.collector(body, self._samples)

                remaining = step.duration_s - (time.perf_counter() - start)
                overlay = frame.copy()
                cv2.putText(
                    overlay,
                    f"Step {i}/{len(steps)}: {step.name}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2,
                )
                cv2.putText(
                    overlay,
                    step.instruction,
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1,
                )
                cv2.putText(
                    overlay,
                    f"Time: {remaining:.1f}s",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 100), 2,
                )
                cv2.imshow("EldenBody Calibration", overlay)
                cv2.waitKey(1)

            print(f"  -> Completed: {step.name}")

        cap.release()
        cv2.destroyAllWindows()
        self._apply_calibration()
        self._pose.close()
        self._hands.close()
        print("\nCalibration saved to settings.json\n")
        return True

    def _apply_calibration(self) -> None:
        cal = {
            "neutral_hip_y": self._avg("neutral_hip_y", 0.5),
            "neutral_hip_x": self._avg("neutral_hip_x", 0.5),
            "neutral_shoulder_y": self._avg("neutral_shoulder_y", 0.35),
            "torso_angle_neutral": self._avg("torso_angle_neutral", 0.0),
            "right_wrist_y": self._avg("right_wrist_y", 0.3),
            "left_wrist_y": self._avg("left_wrist_y", 0.3),
            "sword_hold_angle": self._avg("sword_hold_angle", 0.0),
            "walk_knee_amplitude": max(self._avg("walk_knee_amplitude", 0.02), 0.01),
            "walk_frequency": max(self._avg("walk_frequency", 1.5), 0.5),
            "run_knee_amplitude": max(self._avg("run_knee_amplitude", 0.06), 0.02),
            "run_frequency": max(self._avg("run_frequency", 3.0), 1.0),
            "dodge_bend_angle": max(self._avg("dodge_bend_angle", 25.0), 15.0),
            "jump_hip_delta": max(self._avg("jump_hip_delta", 0.04), 0.02),
            "lean_back_angle": -15.0,
            "strafe_threshold": 0.03,
        }
        self.config.update_section("calibration", cal)
        self.config.calibrated = True
        self.config.save()

    @staticmethod
    def draw_prompt(frame: np.ndarray, text: str) -> np.ndarray:
        out = frame.copy()
        cv2.putText(out, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        return out
