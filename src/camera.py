import os
import subprocess
import threading
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
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[Any] = None
        self._last_frame_at = 0.0
        self._next_start_attempt_at = 0.0
        self._stop_event = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None
        self._start_process()
        self._start_reader_thread()

    def _start_process(self):
        """rpicam-vid를 켜고 stdout으로 MJPEG 프레임을 받는다."""
        if self.proc and self.proc.poll() is None:
            return

        now = time.monotonic()
        if now < self._next_start_attempt_at:
            return
        self._next_start_attempt_at = now + 1.0

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

    def _start_reader_thread(self):
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return

        self._stop_event.clear()
        self._reader_thread = threading.Thread(
            target=self._capture_loop,
            name="CameraCaptureReader",
            daemon=True,
        )
        self._reader_thread.start()

    def _capture_loop(self):
        """카메라 stdout을 계속 비워 최신 프레임만 캐시에 저장한다."""
        while not self._stop_event.is_set():
            latest_jpg = self._read_latest_jpeg_chunk()
            if latest_jpg is None:
                time.sleep(0.001)
                continue

            np_arr = np.frombuffer(latest_jpg, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            with self._frame_lock:
                self._latest_frame = frame
                self._last_frame_at = time.monotonic()

    def _read_latest_jpeg_chunk(self) -> Optional[bytes]:
        if not self.proc or self.proc.stdout is None:
            self._start_process()
            if not self.proc or self.proc.stdout is None:
                return None

        if self.proc.stdout is None:
            return None

        fileno = getattr(self.proc.stdout, "fileno", None)
        fd = fileno() if callable(fileno) else None
        latest_jpg = None

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
                continue

            if chunk == b"" and latest_jpg is not None:
                break

            poll = getattr(self.proc, "poll", None)
            process_ended = poll() is not None if callable(poll) else True
            if chunk == b"" and process_ended:
                # 카메라 프로세스가 죽었으면 다음 루프에서 새로 시작한다.
                self._stop_process()
                self._start_process()
                return None

            break

        return latest_jpg

    def _stop_process(self):
        if not self.proc:
            return

        self.proc.terminate()
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        finally:
            self.proc = None

    def get_frame(self) -> Optional[Any]:
        """백그라운드 캡처 스레드가 저장한 최신 프레임을 즉시 반환한다."""
        self._start_reader_thread()
        with self._frame_lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

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
        self._stop_event.set()
        thread = self._reader_thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1)
        self._reader_thread = None

        if not self.proc:
            return

        self._stop_process()
        print("[Camera] Released")
