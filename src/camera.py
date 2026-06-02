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
        """rpicam-vid를 켜고 stdout으로 MJPEG 프레임을 받는다."""
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
                fileno = getattr(self.proc.stdout, "fileno", None)
                if callable(fileno):
                    # 읽을 데이터가 없을 때 카메라 루프가 멈추지 않도록 non-blocking 처리.
                    os.set_blocking(fileno(), False)
            print(
                f"[Camera] Started rpicam-vid stream "
                f"({self.width}x{self.height} @ {self.fps}fps, cam={self.index})"
            )
        except OSError as exc:
            # 카메라 시작 실패는 치명적이지 않게 두고 다음 get_frame에서 다시 시도한다.
            self.proc = None
            print(f"[Camera] Failed to start rpicam-vid: {exc}")

    def get_frame(self) -> Optional[Any]:
        """버퍼에 쌓인 JPEG 중 가장 최신 프레임을 디코딩해서 반환한다."""
        if not self.proc or self.proc.stdout is None:
            self._start_process()
            if not self.proc or self.proc.stdout is None:
                return None

        if self.proc.stdout is None:
            return None

        fileno = getattr(self.proc.stdout, "fileno", None)
        fd = fileno() if callable(fileno) else None
        latest_jpg = None
        # 저 FPS 카메라도 프레임 누락으로 오해하지 않도록 짧게 기다린다.
        frame_period = 1.0 / max(1, self.fps)
        wait_timeout = min(0.25, max(0.05, frame_period * 2.0))
        deadline = time.monotonic() + wait_timeout

        while True:
            try:
                if fd is None:
                    chunk = self.proc.stdout.read(65536)
                else:
                    chunk = os.read(fd, 65536)
            except BlockingIOError:
                chunk = None

            if chunk:
                self.raw_bytes += chunk
                newest = self._extract_latest_jpeg()
                if newest is not None and len(newest) > 100:
                    latest_jpg = newest
                if len(self.raw_bytes) > 2_000_000:
                    # 깨진 데이터가 계속 쌓이면 메모리만 늘어나므로 버퍼를 비운다.
                    self.raw_bytes = b""
                if time.monotonic() < deadline:
                    continue
                break

            if chunk == b"" and latest_jpg is not None:
                break

            poll = getattr(self.proc, "poll", None)
            process_ended = poll() is not None if callable(poll) else True
            if chunk == b"" and process_ended:
                # 카메라 프로세스가 죽었으면 다음 루프에서 새로 시작한다.
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
        """버퍼에서 완성된 JPEG 프레임을 끝까지 훑어 가장 최신 것만 남긴다."""
        last_frame = None

        while True:
            start = self.raw_bytes.find(b"\xff\xd8")
            if start == -1:
                # JPEG 시작 마커가 없으면 오래된 잡음 버퍼를 정리한다.
                if len(self.raw_bytes) > 1_000_000:
                    self.raw_bytes = b""
                return last_frame

            end = self.raw_bytes.find(b"\xff\xd9", start + 2)
            if end == -1:
                # 아직 덜 받은 JPEG는 보존하고, 앞쪽 쓰레기 데이터는 버린다.
                if start > 0:
                    self.raw_bytes = self.raw_bytes[start:]
                return last_frame

            last_frame = self.raw_bytes[start : end + 2]
            self.raw_bytes = self.raw_bytes[end + 2 :]

    def release(self):
        """rpicam-vid 프로세스를 안전하게 종료한다."""
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
