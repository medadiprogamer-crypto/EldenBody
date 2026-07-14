"""
EldenBody Controller - Main Application Entry Point.

Controls Elden Ring using body movements (webcam) and PS4 gyro (camera).
"""

from __future__ import annotations

import argparse
import queue
import sys
import threading
import time
from typing import Any

import cv2

from calibration.calibration import CalibrationWizard
from config import Config
from controller.mapping import InputMapper
from controller.xbox_controller import XboxController
from gestures.gesture_engine import GestureEngine, GestureResult
from gyro.ps4_gyro import PS4GyroReader
from tracking.body_state import BodyState
from tracking.hand_detector import HandDetector
from tracking.pose_detector import PoseDetector
from utils.debug import DebugOverlay


class EldenBodyApp:
    """Main application orchestrating the control pipeline."""

    def __init__(self, config: Config, force_calibrate: bool = False) -> None:
        self.config = config
        self.force_calibrate = force_calibrate

        self.pose_detector = PoseDetector(config)
        self.hand_detector = HandDetector(config)
        self.gesture_engine = GestureEngine(config)
        self.input_mapper = InputMapper(config)
        self.xbox = XboxController()
        self.gyro = PS4GyroReader(config)
        self.debug = DebugOverlay()

        self._frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self._body_queue: queue.Queue = queue.Queue(maxsize=2)
        self._gesture_queue: queue.Queue = queue.Queue(maxsize=2)

        self._running = False
        self._threads: list[threading.Thread] = []
        self._latest_body: BodyState | None = None
        self._latest_gestures = GestureResult()
        self._lock = threading.Lock()
        self._cap: cv2.VideoCapture | None = None
        self._last_frame: Any = None

    def _maybe_calibrate(self) -> bool:
        if self.force_calibrate or not self.config.calibrated:
            print("Starting calibration wizard...")
            wizard = CalibrationWizard(self.config)
            return wizard.run(self.config.get("camera_index", 0))
        return True

    def _camera_thread(self) -> None:
        """Thread 1: Camera capture + MediaPipe pose/hands."""
        target_fps = self.config.get("target_fps", 60)
        frame_time = 1.0 / target_fps

        while self._running:
            loop_start = time.perf_counter()
            if not self._cap:
                time.sleep(0.01)
                continue

            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            self._last_frame = frame
            body = self.pose_detector.process(frame)
            body = self.hand_detector.process(frame, body)

            with self._lock:
                self._latest_body = body

            try:
                self._body_queue.put_nowait((frame.copy(), body))
            except queue.Full:
                try:
                    self._body_queue.get_nowait()
                    self._body_queue.put_nowait((frame.copy(), body))
                except queue.Empty:
                    pass

            elapsed = time.perf_counter() - loop_start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _gesture_thread(self) -> None:
        """Thread 2: Gesture recognition processing."""
        while self._running:
            try:
                _, body = self._body_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            gestures = self.gesture_engine.process(body)
            with self._lock:
                self._latest_gestures = gestures

            try:
                self._gesture_queue.put_nowait(gestures)
            except queue.Full:
                try:
                    self._gesture_queue.get_nowait()
                    self._gesture_queue.put_nowait(gestures)
                except queue.Empty:
                    pass

    def _controller_thread(self) -> None:
        """Thread 3: Virtual controller + gyro output."""
        update_rate = 1.0 / self.config.get("target_fps", 60)

        while self._running:
            loop_start = time.perf_counter()

            with self._lock:
                gestures = self._latest_gestures
                body = self._latest_body

            state = self.input_mapper.map_gestures(gestures)

            gyro_x, gyro_y = 0.0, 0.0
            if self.gyro.active:
                gyro_x, gyro_y = self.gyro.get_camera_stick()

            if body:
                state = self.input_mapper.apply_head_tracking(body, state, gyro_x, gyro_y)
            else:
                state.right_stick_x = gyro_x
                state.right_stick_y = gyro_y

            self.xbox.update(state)

            elapsed = time.perf_counter() - loop_start
            sleep_time = update_rate - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _build_hud(self) -> dict[str, str]:
        with self._lock:
            gestures = self._latest_gestures
            body = self._latest_body

        action = gestures.primary_action
        controller_status = "Connected" if self.xbox.connected else "Disconnected"
        gyro_status = "Active" if self.gyro.active else "Inactive"

        hud = {
            "action": action,
            "controller": controller_status,
            "gyro": gyro_status,
            "movement": gestures.movement.action_label,
            "combat": gestures.combat.action_label,
        }

        if body and body.valid:
            mov = gestures.movement
            hud["left_stick"] = f"({mov.stick_x:.2f}, {mov.stick_y:.2f})"
            gx, gy = self.gyro.get_camera_stick()
            hud["right_stick"] = f"({gx:.2f}, {gy:.2f})"

        return hud

    def run(self) -> None:
        if not self._maybe_calibrate():
            print("Calibration failed. Exiting.")
            return

        camera_index = self.config.get("camera_index", 0)
        # تغییر شده: حذف cv2.CAP_DSHOW
        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            print(f"ERROR: Cannot open camera index {camera_index}")
            sys.exit(1)

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.get("camera_width", 640))
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.get("camera_height", 480))
        self._cap.set(cv2.CAP_PROP_FPS, self.config.get("target_fps", 60))
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        gyro_started = self.gyro.start()
        if gyro_started:
            print("PS4 Gyro: Connected and active")
        else:
            print("PS4 Gyro: Not detected (camera will use head tracking if enabled)")

        self._running = True
        self._threads = [
            threading.Thread(target=self._camera_thread, daemon=True, name="Camera"),
            threading.Thread(target=self._gesture_thread, daemon=True, name="Gestures"),
            threading.Thread(target=self._controller_thread, daemon=True, name="Controller"),
        ]
        for t in self._threads:
            t.start()

        print("\n=== EldenBody Controller Running ===")
        print("Press Q to quit | Press R to recalibrate | Press D to toggle debug\n")

        debug_mode = self.config.get("debug_mode", True)

        try:
            while self._running:
                if self._last_frame is None:
                    time.sleep(0.01)
                    continue

                frame = self._last_frame
                with self._lock:
                    body = self._latest_body

                if debug_mode:
                    pose_lm = body.pose_landmarks if body else None
                    left_lm = body.left_hand.landmarks if body and body.left_hand.detected else None
                    right_lm = body.right_hand.landmarks if body and body.right_hand.detected else None
                    hud = self._build_hud()
                    display = self.debug.draw(frame, pose_lm, left_lm, right_lm, hud)
                    cv2.imshow("EldenBody Controller", display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("r"):
                    self._running = False
                    for t in self._threads:
                        t.join(timeout=1.0)
                    self._cleanup_capture()
                    wizard = CalibrationWizard(self.config)
                    wizard.run(camera_index)
                    self._running = True
                    # تغییر شده: حذف cv2.CAP_DSHOW
                    self._cap = cv2.VideoCapture(camera_index)
                    self._threads = [
                        threading.Thread(target=self._camera_thread, daemon=True, name="Camera"),
                        threading.Thread(target=self._gesture_thread, daemon=True, name="Gestures"),
                        threading.Thread(target=self._controller_thread, daemon=True, name="Controller"),
                    ]
                    for t in self._threads:
                        t.start()
                elif key == ord("d"):
                    debug_mode = not debug_mode
                    if not debug_mode:
                        cv2.destroyWindow("EldenBody Controller")

        except KeyboardInterrupt:
            print("\nInterrupted.")
        finally:
            self.shutdown()

    def _cleanup_capture(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def shutdown(self) -> None:
        self._running = False
        for t in self._threads:
            t.join(timeout=1.0)
        self.xbox.release()
        self.gyro.stop()
        self.pose_detector.close()
        self.hand_detector.close()
        self._cleanup_capture()
        cv2.destroyAllWindows()
        print("EldenBody Controller stopped.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EldenBody Controller for Elden Ring")
    parser.add_argument("--calibrate", action="store_true", help="Force calibration on launch")
    parser.add_argument("--no-debug", action="store_true", help="Disable debug overlay")
    parser.add_argument("--camera", type=int, default=None, help="Camera index override")
    parser.add_argument("--no-gyro", action="store_true", help="Disable PS4 gyro")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = Config()

    if args.no_debug:
        config.set("debug_mode", False)
    if args.camera is not None:
        config.set("camera_index", args.camera)
    if args.no_gyro:
        config.set("use_ps4_gyro", False)

    app = EldenBodyApp(config, force_calibrate=args.calibrate)
    app.run()


if __name__ == "__main__":
    main()