import os
import subprocess
import time
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
            "--low-latency",
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
            if self.proc.stdout is not None:
                os.set_blocking(self.proc.stdout.fileno(), False)
            print(
                f"[Camera] Started rpicam-vid stream "
                f"({self.width}x{self.height} @ {self.fps}fps, cam={self.index})"
            )
        except OSError as exc:
            # Non-fatal: caller loop will keep retrying by checking get_frame() == None.
            self.proc = None
            print(f"[Camera] Failed to start rpicam-vid: {exc}")

    def get_frame(self) -> Optional[Any]:
        """Read and decode the newest available JPEG frame with minimal latency."""
        if not self.proc or self.proc.stdout is None:
            self._start_process()
            if not self.proc or self.proc.stdout is None:
                return None

        if self.proc.stdout is None:
            return None

        fd = self.proc.stdout.fileno()
        latest_jpg = None
        deadline = time.monotonic() + 0.03

        while True:
            try:
                chunk = os.read(fd, 65536)
            except BlockingIOError:
                chunk = None

            if chunk:
                self.raw_bytes += chunk
                newest = self._extract_latest_jpeg()
                if newest is not None and len(newest) > 100:
                    latest_jpg = newest
                if len(self.raw_bytes) > 2_000_000:
                    self.raw_bytes = b""
                if time.monotonic() < deadline:
                    continue
                break

            if chunk == b"" and self.proc.poll() is not None:
                # Stream ended unexpectedly; restart for next loop cycle.
                self.release()
                self._start_process()
                return None

            if latest_jpg is not None or time.monotonic() >= deadline:
                break
            time.sleep(0.001)

        if latest_jpg is None:
            return None

        np_arr = np.frombuffer(latest_jpg, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame

    def _extract_latest_jpeg(self) -> Optional[bytes]:
        """Extract and return the newest complete JPEG frame from the buffer."""
        last_frame = None

        while True:
            start = self.raw_bytes.find(b"\xff\xd8")
            if start == -1:
                # No JPEG start marker in buffer.
                if len(self.raw_bytes) > 1_000_000:
                    self.raw_bytes = b""
                return last_frame

            end = self.raw_bytes.find(b"\xff\xd9", start + 2)
            if end == -1:
                # Keep partial JPEG from latest start marker and drop stale prefix noise.
                if start > 0:
                    self.raw_bytes = self.raw_bytes[start:]
                return last_frame

            last_frame = self.raw_bytes[start : end + 2]
            self.raw_bytes = self.raw_bytes[end + 2 :]

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
