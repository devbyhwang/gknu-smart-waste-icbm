import os
import sys
import threading

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from camera import CameraManager


def test_get_frame_returns_cached_latest_frame_copy():
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    frame[0, 0] = [10, 20, 30]

    camera = CameraManager.__new__(CameraManager)
    camera._frame_lock = threading.Lock()
    camera._latest_frame = frame
    camera._start_reader_thread = lambda: None

    result = camera.get_frame()

    assert np.array_equal(result, frame)
    assert result is not frame

    result[0, 0] = [99, 99, 99]
    assert np.array_equal(frame[0, 0], [10, 20, 30])
