"""Configuration loader and persistence for EldenBody Controller."""

from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any

SETTINGS_PATH = Path(__file__).parent / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "calibrated": False,
    "camera_index": 0,
    "camera_width": 640,
    "camera_height": 480,
    "target_fps": 60,
    "debug_mode": True,
    "use_head_tracking": False,
    "use_ps4_gyro": True,
    "calibration": {},
    "movement": {},
    "combat": {},
    "left_hand": {},
    "magic": {},
    "gyro": {},
    "head_tracking": {},
    "filtering": {},
}


class Config:
    """Thread-safe configuration accessor with JSON persistence."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or SETTINGS_PATH
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = copy.deepcopy(DEFAULT_SETTINGS)
            self.save()

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def section(self, name: str) -> dict[str, Any]:
        return self._data.setdefault(name, {})

    def update_section(self, name: str, values: dict[str, Any]) -> None:
        section = self.section(name)
        section.update(values)
        self._data[name] = section

    @property
    def calibrated(self) -> bool:
        return bool(self._data.get("calibrated", False))

    @calibrated.setter
    def calibrated(self, value: bool) -> None:
        self._data["calibrated"] = value

    def calibration_value(self, key: str, default: float = 0.0) -> float:
        return float(self.section("calibration").get(key, default))

    def movement_value(self, key: str, default: float = 0.0) -> float:
        return float(self.section("movement").get(key, default))

    def combat_value(self, key: str, default: float = 0.0) -> float:
        return float(self.section("combat").get(key, default))

    def gyro_value(self, key: str, default: float = 0.0) -> float:
        return float(self.section("gyro").get(key, default))

    def gyro_bool(self, key: str, default: bool = False) -> bool:
        return bool(self.section("gyro").get(key, default))
