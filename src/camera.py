from typing import Any, Optional

import cv2


class CameraManager:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 15):
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None
        self._open_camera()

    def _open_camera(self):
        self.release()
        self.cap = cv2.VideoCapture(self.index)
        if self.cap is None or not self.cap.isOpened():
            self.cap = None
            print(f"[Camera] Failed to open camera index={self.index}")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))
        self.cap.set(cv2.CAP_PROP_FPS, float(self.fps))
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1.0)
        print(f"[Camera] Opened cv2 camera ({self.width}x{self.height} @ {self.fps}fps, cam={self.index})")

    def get_frame(self) -> Optional[Any]:
        """Read one frame from cv2.VideoCapture."""
        if self.cap is None or not self.cap.isOpened():
            self._open_camera()
            if self.cap is None or not self.cap.isOpened():
                return None

        ok, frame = self.cap.read()
        if not ok or frame is None:
            self._open_camera()
            return None
        return frame

    def release(self):
        """Safely release cv2 capture."""
        if self.cap is None:
            return

        self.cap.release()
        self.cap = None
        print("[Camera] Released")
