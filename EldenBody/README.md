# EldenBody Controller

Control **Elden Ring** using your body movements through a laptop webcam, with PS4 DualShock 4 gyroscope for camera control.

## Features

- **Full-body locomotion**: walk, sprint, strafe, dodge, jump
- **Sword combat**: light/heavy attacks, charged attacks, thrusts, diagonal and upper slashes
- **Left hand**: block, weapon skill, flask heal
- **Magic gestures**: cast and spell attack
- **PS4 gyro camera**: yaw/pitch mapped to right stick with dead zone and smoothing
- **Calibration wizard**: personalized thresholds saved to `settings.json`
- **Debug overlay**: skeleton, hands, FPS, action labels, controller/gyro status
- **Multi-threaded pipeline**: 60 FPS target with low latency

## Hardware Requirements

| Component | Requirement |
|-----------|-------------|
| Laptop | Acer Nitro ANV15-51 or similar |
| Webcam | Built-in laptop camera |
| Controller | PS4 DualShock 4 (USB, gyro only) |
| Driver | ViGEmBus (virtual Xbox 360 controller) |
| OS | Windows 10/11 |

## Project Structure

```
EldenBody/
├── main.py                 # Application entry point
├── config.py               # Settings loader
├── settings.json           # User calibration & tuning
├── tracking/               # MediaPipe pose + hands
├── gestures/               # Movement, combat, magic, items
├── controller/             # Virtual Xbox output (vgamepad)
├── gyro/                   # PS4 gyro HID reader
├── calibration/            # First-launch wizard
└── utils/                  # Filters, debug overlay
```

## Installation

### 1. Prerequisites

- Python 3.10+ installed and in PATH
- ViGEmBus driver installed ([download](https://github.com/nefarius/ViGEmBus/releases))
- PS4 controller connected via **USB** (for gyro)

### 2. Install dependencies

Double-click `install.bat` or run:

```bat
cd C:\Users\medad\EldenBody
install.bat
```

Or manually:

```bat
pip install -r requirements.txt
```

## Running

Double-click `run.bat` or:

```bat
python main.py
```

### Command-line options

```bat
python main.py --calibrate    # Force calibration on launch
python main.py --no-debug     # Hide debug window
python main.py --camera 0     # Select camera index
python main.py --no-gyro      # Disable PS4 gyro
```

## First Launch — Calibration

On first run, a guided calibration walks you through:

1. Stand normally
2. Raise right hand (sword hand)
3. Raise left hand
4. Hold sword ready position
5. Walk in place
6. Run in place
7. Dodge motion (forward bend)
8. Jump

Values are saved to `settings.json`. Press **R** during gameplay to recalibrate.

## Control Mapping

### Movement (Body)

| Action | Input |
|--------|-------|
| Walk in place | Left stick forward |
| Run in place (high knees) | Left stick forward + L3 (sprint) |
| Lean backward | Left stick back |
| Hip strafe left/right | Left stick X |
| Quick forward bend | B (dodge roll) |
| Jump | A |

### Right Hand (Sword / Tube)

| Gesture | Input |
|---------|-------|
| Fast horizontal swing | RB (light attack) |
| Slow powerful swing | RT (heavy attack) |
| Backward hold → forward swing | RT (charged heavy) |
| Diagonal downward swing | RT (heavy) |
| Upward swing | RT (upper slash) |
| Thrust forward | RB (thrust) |

### Left Hand

| Gesture | Input |
|---------|-------|
| Open palm | LB (block) |
| Casting gesture | LT (weapon skill) |
| Hand at chest (hold) | X (flask heal) |

### Magic

| Gesture | Input |
|---------|-------|
| Raise left hand | LT (cast) |
| Forward hand thrust | RB (spell attack) |

### Camera

| Source | Input |
|--------|-------|
| PS4 gyro yaw | Right stick X |
| PS4 gyro pitch | Right stick Y |
| Head tracking (optional) | Blended with gyro |

## Elden Ring Setup

1. **Close Steam Input** or disable PlayStation configuration for the virtual Xbox pad
2. Launch Elden Ring
3. Go to **Settings → Controls**
4. Confirm **Xbox** controller layout is active
5. Adjust in-game camera sensitivity to taste (EldenBody handles gyro scaling in `settings.json`)

### Recommended settings.json tweaks

```json
"gyro": {
  "sensitivity_yaw": 1.5,
  "sensitivity_pitch": 1.2,
  "deadzone": 0.05,
  "smoothing": 0.25
}
```

## Performance Tips

- Run on **AC power** for consistent 60 FPS
- Close other camera apps (Teams, Zoom)
- Use a well-lit room facing the camera
- Hold sword (tube) clearly in right hand view
- USB PS4 connection required — Bluetooth gyro latency is higher

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No virtual controller in game | Reinstall ViGEmBus, run as Administrator |
| PS4 gyro inactive | Connect via USB; only one input device should claim DS4 |
| False attacks | Increase `attack_cooldown_ms` or `confidence_threshold` in settings.json |
| Walk not detected | Recalibrate (press R) |
| Low FPS | Lower `camera_width`/`camera_height` in settings.json |

## Keyboard Shortcuts (Debug Window)

| Key | Action |
|-----|--------|
| Q | Quit |
| R | Recalibrate |
| D | Toggle debug overlay |

## License

Personal use project. Elden Ring is a trademark of FromSoftware/Bandai Namco.
