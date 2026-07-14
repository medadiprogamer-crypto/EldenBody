"""PS4 DualShock 4 gyroscope reader for camera control."""

from __future__ import annotations

import struct
import threading
import time
from typing import Any

from config import Config
from utils.filters import DeadZone, ExponentialMovingAverage

# DS4 USB identifiers
DS4_VID = 0x054C
DS4_PID_USB = 0x05C4
DS4_PID_USB_V2 = 0x09CC
DS4_PID_BT = 0x0BA0

try:
    import hid
    HID_AVAILABLE = True
except ImportError:
    hid = None  # type: ignore
    HID_AVAILABLE = False


class PS4GyroReader:
    """Read gyroscope data from physical PS4 controller via HID."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._device: Any | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self._gyro_x = 0.0
        self._gyro_y = 0.0
        self._gyro_z = 0.0
        self._stick_x = 0.0
        self._stick_y = 0.0
        self._active = False
        self._gyro_bias = {"x": 0.0, "y": 0.0, "z": 0.0}
        self._bias_samples: list[tuple[float, float, float]] = []

        gyro_cfg = config.section("gyro")
        self._yaw_ema = ExponentialMovingAverage(gyro_cfg.get("smoothing", 0.25))
        self._pitch_ema = ExponentialMovingAverage(gyro_cfg.get("smoothing", 0.25))
        self._deadzone = DeadZone(gyro_cfg.get("deadzone", 0.05))

    @property
    def active(self) -> bool:
        return self._active and self._running

    @property
    def available(self) -> bool:
        return HID_AVAILABLE

    def _find_device(self) -> Any | None:
        if not HID_AVAILABLE:
            return None
        for pid in (DS4_PID_USB, DS4_PID_USB_V2, DS4_PID_BT):
            try:
                dev = hid.device()
                dev.open(DS4_VID, pid)
                dev.set_nonblocking(True)
                return dev
            except Exception:
                continue
        # Enumerate all HID devices
        try:
            for info in hid.enumerate(DS4_VID, 0):
                pid = info.get("product_id", 0)
                if pid in (DS4_PID_USB, DS4_PID_USB_V2, DS4_PID_BT):
                    dev = hid.device()
                    dev.open_path(info["path"])
                    dev.set_nonblocking(True)
                    return dev
        except Exception:
            pass
        return None

    def start(self) -> bool:
        if not self.config.get("use_ps4_gyro", True):
            return False
        if not HID_AVAILABLE:
            return False

        self._device = self._find_device()
        if not self._device:
            return False

        self._running = True
        self._active = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True, name="PS4Gyro")
        self._thread.start()
        return True

    def _parse_gyro(self, data: bytes) -> tuple[float, float, float] | None:
        if len(data) < 20:
            return None

        # DS4 input report: gyro at bytes 13-18 (little-endian int16)
        offset = 0
        if data[0] in (0x01, 0x11):
            offset = 1 if data[0] == 0x01 else 3

        try:
            gx = struct.unpack_from("<h", data, offset + 12)[0]
            gy = struct.unpack_from("<h", data, offset + 14)[0]
            gz = struct.unpack_from("<h", data, offset + 16)[0]
        except struct.error:
            return None

        # Convert to deg/s scale (DS4 gyro unit ~ 1/16 deg/s per LSB approx)
        scale = 1.0 / 128.0
        return gx * scale, gy * scale, gz * scale

    def _calibrate_bias(self, gx: float, gy: float, gz: float) -> None:
        self._bias_samples.append((gx, gy, gz))
        if len(self._bias_samples) >= 60:
            n = len(self._bias_samples)
            self._gyro_bias["x"] = sum(s[0] for s in self._bias_samples) / n
            self._gyro_bias["y"] = sum(s[1] for s in self._bias_samples) / n
            self._gyro_bias["z"] = sum(s[2] for s in self._bias_samples) / n
            self._bias_samples.clear()

    def _read_loop(self) -> None:
        while self._running and self._device:
            try:
                data = self._device.read(64)
                if not data:
                    time.sleep(0.001)
                    continue

                raw = self._parse_gyro(bytes(data))
                if raw is None:
                    continue

                gx, gy, gz = raw
                if len(self._bias_samples) > 0 or len(self._bias_samples) == 0 and self._gyro_bias["x"] == 0:
                    self._calibrate_bias(gx, gy, gz)

                gx -= self._gyro_bias["x"]
                gy -= self._gyro_bias["y"]
                gz -= self._gyro_bias["z"]

                gyro_cfg = self.config.section("gyro")
                yaw_sens = gyro_cfg.get("sensitivity_yaw", 1.5)
                pitch_sens = gyro_cfg.get("sensitivity_pitch", 1.2)
                max_out = gyro_cfg.get("max_stick_output", 0.95)
                invert_yaw = gyro_cfg.get("invert_yaw", False)
                invert_pitch = gyro_cfg.get("invert_pitch", True)

                # Yaw from Z rotation, Pitch from Y rotation
                yaw = gz * yaw_sens * 0.02
                pitch = gy * pitch_sens * 0.02
                if invert_yaw:
                    yaw = -yaw
                if invert_pitch:
                    pitch = -pitch

                yaw = max(-max_out, min(max_out, self._yaw_ema.update(yaw)))
                pitch = max(-max_out, min(max_out, self._pitch_ema.update(pitch)))
                stick_x, stick_y = self._deadzone.apply(yaw, pitch)

                with self._lock:
                    self._gyro_x, self._gyro_y, self._gyro_z = gx, gy, gz
                    self._stick_x = stick_x
                    self._stick_y = stick_y
                    self._active = True

            except Exception:
                with self._lock:
                    self._active = False
                time.sleep(0.05)

    def get_camera_stick(self) -> tuple[float, float]:
        with self._lock:
            return self._stick_x, self._stick_y

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
        self._active = False
