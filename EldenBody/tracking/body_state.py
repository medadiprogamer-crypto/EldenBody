"""Shared body state representation from pose and hand tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HandState:
    """Tracked state for a single hand."""

    detected: bool = False
    landmarks: Any | None = None
    wrist: tuple[float, float, float] = (0.0, 0.0, 0.0)
    index_tip: tuple[float, float, float] = (0.0, 0.0, 0.0)
    middle_tip: tuple[float, float, float] = (0.0, 0.0, 0.0)
    palm_center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    acceleration: tuple[float, float, float] = (0.0, 0.0, 0.0)
    speed: float = 0.0
    swing_angle: float = 0.0
    swing_direction: str = "none"
    fingers_extended: bool = False
    palm_open: bool = False
    confidence: float = 0.0
    is_raised: bool = False
    near_chest: bool = False


@dataclass
class BodyState:
    """Complete tracked body state for one frame."""

    timestamp: float = 0.0
    frame_id: int = 0
    pose_landmarks: Any | None = None
    pose_world_landmarks: Any | None = None

    # Core body metrics
    hip_center: tuple[float, float] = (0.5, 0.5)
    shoulder_center: tuple[float, float] = (0.5, 0.35)
    nose: tuple[float, float] = (0.5, 0.2)
    torso_angle: float = 0.0
    lean_forward: float = 0.0
    lean_backward: float = 0.0
    head_yaw: float = 0.0
    head_pitch: float = 0.0

    # Leg metrics
    left_knee_y: float = 0.0
    right_knee_y: float = 0.0
    left_ankle_y: float = 0.0
    right_ankle_y: float = 0.0
    knee_lift_avg: float = 0.0
    leg_oscillation: float = 0.0
    leg_frequency: float = 0.0
    is_walking: bool = False
    is_sprinting: bool = False

    # Movement events
    is_jumping: bool = False
    is_dodging: bool = False
    hip_delta_y: float = 0.0
    strafe_offset: float = 0.0

    # Hands
    left_hand: HandState = field(default_factory=HandState)
    right_hand: HandState = field(default_factory=HandState)

    pose_confidence: float = 0.0
    valid: bool = False
