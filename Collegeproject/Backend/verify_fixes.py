import os
import sys
import numpy as np

# Add Backend to sys.path
sys.path.append(os.getcwd())

# Mock Django setup if needed, but we can test ml_utils directly
from detections.ml_utils import detect_speech_in_audio

def test_vad():
    print("Testing VAD safety check...")
    # Test with None
    try:
        res = detect_speech_in_audio(None, 16000)
        print(f"None check: {res} (Expected: False)")
    except Exception as e:
        print(f"None check failed with error: {e}")

    # Test with empty array
    try:
        res = detect_speech_in_audio(np.array([]), 16000)
        print(f"Empty array check: {res} (Expected: False)")
    except Exception as e:
        print(f"Empty array check failed with error: {e}")

    # Test with very short array
    try:
        res = detect_speech_in_audio(np.zeros(100, dtype=np.float32), 16000)
        print(f"Short array check: {res} (Expected: False)")
    except Exception as e:
        print(f"Short array check failed with error: {e}")

    # Test with sufficient length (zeros)
    try:
        res = detect_speech_in_audio(np.zeros(1000, dtype=np.float32), 16000)
        print(f"Long zero array check: {res}")
    except Exception as e:
        print(f"Long zero array check failed with error: {e}")

if __name__ == "__main__":
    # Note: This requires the virtual environment and installed dependencies
    test_vad()
