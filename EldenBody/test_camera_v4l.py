"""Test camera with different backends."""

import cv2

print("=== Testing Alternative Backends ===\n")

backends = [
    (cv2.CAP_V4L, "V4L (Linux Video)"),
    (cv2.CAP_VFW, "VFW (Video for Windows)"),
    (cv2.CAP_AVFOUNDATION, "AVFoundation"),
    (cv2.CAP_WINRT, "WinRT"),
    (cv2.CAP_MSMF, "MediaFoundation (MSMF)"),
]

# تست بدون backend مشخص (default)
print("Testing with default backend...\n")
for i in range(3):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"✓ Camera index {i}: FOUND (default backend)")
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"  Resolution: {width} x {height}")
        print(f"  FPS: {fps}\n")
        
        ret, frame = cap.read()
        if ret:
            print(f"  ✓ Frame read successfully")
        else:
            print(f"  ✗ Failed to read frame")
        
        cap.release()
    else:
        print(f"✗ Camera index {i}: not available (default)\n")

print("\n" + "="*50 + "\n")
print("Testing with specific backends...\n")

for backend_id, backend_name in backends:
    try:
        cap = cv2.VideoCapture(0, backend_id)
        if cap.isOpened():
            print(f"✓ {backend_name}: WORKS!")
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            print(f"  Resolution: {width} x {height}\n")
            cap.release()
        else:
            print(f"✗ {backend_name}: not working\n")
    except Exception as e:
        print(f"✗ {backend_name}: error - {e}\n")

print("Done!")