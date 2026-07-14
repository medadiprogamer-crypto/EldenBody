"""Test camera with different backends - Advanced diagnostics."""

import cv2
import sys

print("=== Advanced Camera Diagnostics ===\n")

# Test 1: List all available cameras
print("Test 1: Checking available cameras...\n")
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"✓ Camera index {i}: FOUND")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        print(f"  Resolution: {width} x {height}, FPS: {fps}")
        
        ret, frame = cap.read()
        if ret:
            print(f"  ✓ Frame captured successfully\n")
        else:
            print(f"  ✗ Failed to capture frame\n")
        cap.release()

print("="*50 + "\n")

# Test 2: Test MediaFoundation backend
print("Test 2: Testing MediaFoundation (MSMF) backend...\n")
try:
    cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
    if cap.isOpened():
        print(f"✓ MSMF Backend: WORKS")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"  Resolution: {width} x {height}")
        
        ret, frame = cap.read()
        if ret:
            print(f"  ✓ Frame read: SUCCESS")
        cap.release()
    else:
        print(f"✗ MSMF Backend: FAILED\n")
except Exception as e:
    print(f"✗ MSMF Backend error: {e}\n")

print("="*50 + "\n")

# Test 3: OpenCV Info
print("Test 3: OpenCV Information:\n")
print(f"OpenCV Version: {cv2.__version__}")
print(f"Python Version: {sys.version}")

print("\n" + "="*50)
print("If all tests show ✗, your camera may be:")
print("- Not connected properly")
print("- Used by another application")
print("- Disabled in Device Manager")
print("- Driver issue")
print("="*50)
