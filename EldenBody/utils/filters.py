"""Signal filtering utilities for motion and input stabilization."""

from __future__ import annotations

import time
from collections import deque
from typing import Deque


class ExponentialMovingAverage:
    """Exponential moving average filter for scalar values."""

    def __init__(self, alpha: float = 0.3, initial: float = 0.0) -> None:
        self.alpha = max(0.01, min(1.0, alpha))
        self._value = initial
        self._initialized = False

    def update(self, value: float) -> float:
        if not self._initialized:
            self._value = value
            self._initialized = True
        else:
            self._value = self.alpha * value + (1.0 - self.alpha) * self._value
        return self._value

    @property
    def value(self) -> float:
        return self._value

    def reset(self, value: float = 0.0) -> None:
        self._value = value
        self._initialized = False


class VectorEMA:
    """EMA filter for 2D/3D vectors."""

    def __init__(self, alpha: float = 0.3, dims: int = 3) -> None:
        self.filters = [ExponentialMovingAverage(alpha) for _ in range(dims)]

    def update(self, values: tuple[float, ...]) -> tuple[float, ...]:
        return tuple(f.update(v) for f, v in zip(self.filters, values))

    def reset(self) -> None:
        for f in self.filters:
            f.reset()


class DeadZone:
    """Apply radial dead zone to stick-like inputs."""

    def __init__(self, deadzone: float = 0.08) -> None:
        self.deadzone = deadzone

    def apply(self, x: float, y: float) -> tuple[float, float]:
        magnitude = (x * x + y * y) ** 0.5
        if magnitude < self.deadzone:
            return 0.0, 0.0
        scale = (magnitude - self.deadzone) / (1.0 - self.deadzone)
        scale = min(1.0, scale) / magnitude
        return x * scale, y * scale

    def apply_scalar(self, value: float) -> float:
        if abs(value) < self.deadzone:
            return 0.0
        sign = 1.0 if value > 0 else -1.0
        return sign * (abs(value) - self.deadzone) / (1.0 - self.deadzone)


class CooldownManager:
    """Per-action cooldown to prevent accidental repeated inputs."""

    def __init__(self) -> None:
        self._last_fire: dict[str, float] = {}

    def ready(self, action: str, cooldown_ms: float) -> bool:
        now = time.perf_counter() * 1000.0
        last = self._last_fire.get(action, 0.0)
        return (now - last) >= cooldown_ms

    def fire(self, action: str) -> None:
        self._last_fire[action] = time.perf_counter() * 1000.0

    def try_fire(self, action: str, cooldown_ms: float) -> bool:
        if self.ready(action, cooldown_ms):
            self.fire(action)
            return True
        return False


class HoldDetector:
    """Detect sustained pose/gesture holds."""

    def __init__(self, hold_ms: float) -> None:
        self.hold_ms = hold_ms
        self._start: float | None = None

    def update(self, active: bool) -> bool:
        now = time.perf_counter() * 1000.0
        if active:
            if self._start is None:
                self._start = now
            return (now - self._start) >= self.hold_ms
        self._start = None
        return False

    def reset(self) -> None:
        self._start = None


class VelocityTracker:
    """Track velocity and acceleration from position history."""

    def __init__(self, window: int = 5, smoothing: float = 0.3) -> None:
        self._history: Deque[tuple[float, tuple[float, float, float]]] = deque(maxlen=window)
        self._velocity_ema = VectorEMA(smoothing, 3)
        self._accel_ema = VectorEMA(smoothing, 3)
        self._last_velocity = (0.0, 0.0, 0.0)

    def update(self, position: tuple[float, float, float], timestamp: float) -> dict:
        self._history.append((timestamp, position))
        if len(self._history) < 2:
            return {
                "velocity": (0.0, 0.0, 0.0),
                "acceleration": (0.0, 0.0, 0.0),
                "speed": 0.0,
            }

        t0, p0 = self._history[-2]
        t1, p1 = self._history[-1]
        dt = max(t1 - t0, 1e-6)
        raw_vel = tuple((a - b) / dt for a, b in zip(p1, p0))
        velocity = self._velocity_ema.update(raw_vel)
        accel = tuple((a - b) / dt for a, b in zip(velocity, self._last_velocity))
        acceleration = self._accel_ema.update(accel)
        self._last_velocity = velocity
        speed = (velocity[0] ** 2 + velocity[1] ** 2 + velocity[2] ** 2) ** 0.5
        return {
            "velocity": velocity,
            "acceleration": acceleration,
            "speed": speed,
        }


class ConfidenceChecker:
    """Aggregate visibility/confidence scores from landmarks."""

    @staticmethod
    def average(visibilities: list[float], threshold: float = 0.5) -> float:
        if not visibilities:
            return 0.0
        avg = sum(visibilities) / len(visibilities)
        return avg if avg >= threshold else avg * 0.5

    @staticmethod
    def is_confident(visibilities: list[float], threshold: float = 0.6) -> bool:
        if not visibilities:
            return False
        return (sum(visibilities) / len(visibilities)) >= threshold


class LowPassFilter:
    """Simple first-order low-pass filter."""

    def __init__(self, cutoff_factor: float = 0.2) -> None:
        self.factor = cutoff_factor
        self._value = 0.0
        self._init = False

    def filter(self, value: float) -> float:
        if not self._init:
            self._value = value
            self._init = True
        else:
            self._value += self.factor * (value - self._value)
        return self._value
