import subprocess
from typing import Any, Optional

import cv2
import numpy as np


class CameraManager:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 15):
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.proc: Optional[subprocess.Popen] = None
        self.raw_bytes = b""
        self._start_process()

    def _start_process(self):
        """Start rpicam-vid and stream MJPEG frames via stdout."""
        command = [
            "rpicam-vid",
            "-t",
            "0",
            "--camera",
            str(self.index),
            "--width",
            str(self.width),
            "--height",
            str(self.height),
            "--framerate",
            str(self.fps),
            "--codec",
            "mjpeg",
            "--inline",
            "--nopreview",
            "-o",
            "-",
        ]
        try:
            self.proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=10**6,
            )
            print(
                f"[Camera] Started rpicam-vid stream "
                f"({self.width}x{self.height} @ {self.fps}fps, cam={self.index})"
            )
        except OSError as exc:
            # Non-fatal: caller loop will keep retrying by checking get_frame() == None.
            self.proc = None
            print(f"[Camera] Failed to start rpicam-vid: {exc}")

    def get_frame(self) -> Optional[Any]:
        """Read bytes from MJPEG stream, decode one JPEG frame, and return it."""
        if not self.proc or self.proc.stdout is None:
            self._start_process()
            if not self.proc or self.proc.stdout is None:
                return None

        while True:
            if self.proc.stdout is None:
                return None

            chunk = self.proc.stdout.read(4096)
            if not chunk:
                # Stream ended unexpectedly; restart for next loop cycle.
                self.release()
                self._start_process()
                return None

            self.raw_bytes += chunk

            start = self.raw_bytes.find(b"\xff\xd8")
            end = self.raw_bytes.find(b"\xff\xd9")

            if start != -1 and end != -1 and end > start:
                jpg_data = self.raw_bytes[start : end + 2]
                self.raw_bytes = self.raw_bytes[end + 2 :]

                if len(self.raw_bytes) > 1_000_000:
                    self.raw_bytes = b""

                if len(jpg_data) > 100:
                    np_arr = np.frombuffer(jpg_data, dtype=np.uint8)
                    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        return frame

            if len(self.raw_bytes) > 2_000_000:
                self.raw_bytes = b""

    def release(self):
        """Safely terminate rpicam-vid process."""
        if not self.proc:
            return

        self.proc.terminate()
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        finally:
            self.proc = None

        print("[Camera] Released")
