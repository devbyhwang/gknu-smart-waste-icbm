import importlib
import subprocess
import sys
import types


class _FakeStdout:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def read(self, _size):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class _FakeProc:
    def __init__(self, chunks):
        self.stdout = _FakeStdout(chunks)
        self.terminated = False
        self.killed = False
        self.wait_called = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.wait_called = True
        return 0

    def kill(self):
        self.killed = True


def _load_camera_module(monkeypatch, *, chunks=None, wait_timeout=False):
    popen_calls = []
    fake_proc = _FakeProc(chunks or [])

    def fake_popen(command, stdout=None, stderr=None, bufsize=None):
        popen_calls.append(
            {
                "command": command,
                "stdout": stdout,
                "stderr": stderr,
                "bufsize": bufsize,
            }
        )
        return fake_proc

    if wait_timeout:
        def timeout_wait(timeout=None):
            raise subprocess.TimeoutExpired(cmd="rpicam-vid", timeout=timeout)

        fake_proc.wait = timeout_wait

    decoded_frames = []

    def fake_imdecode(np_arr, _flags):
        raw = bytes(np_arr.tolist())
        decoded_frames.append(raw)
        if len(raw) > 100 and raw.startswith(b"\xff\xd8") and raw.endswith(b"\xff\xd9"):
            return "decoded-frame"
        return None

    fake_cv2 = types.SimpleNamespace(imdecode=fake_imdecode, IMREAD_COLOR=1)

    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    sys.modules.pop("src.camera", None)
    camera_module = importlib.import_module("src.camera")
    return camera_module, fake_proc, popen_calls, decoded_frames


def test_camera_start_process_command_and_get_frame_success(monkeypatch):
    jpg = b"\xff\xd8" + (b"x" * 128) + b"\xff\xd9"
    chunks = [b"noise", jpg[:80], jpg[80:], b""]
    camera_module, _proc, popen_calls, _decoded = _load_camera_module(
        monkeypatch, chunks=chunks
    )

    camera = camera_module.CameraManager(index=1, width=800, height=600, fps=20)
    frame = camera.get_frame()

    assert frame == "decoded-frame"
    cmd = popen_calls[0]["command"]
    assert cmd[:3] == ["rpicam-vid", "-t", "0"]
    assert "--camera" in cmd and "1" in cmd
    assert "--width" in cmd and "800" in cmd
    assert "--height" in cmd and "600" in cmd
    assert "--framerate" in cmd and "20" in cmd
    assert "--codec" in cmd and "mjpeg" in cmd


def test_camera_get_frame_none_when_stream_ends(monkeypatch):
    camera_module, _proc, _popen_calls, _decoded = _load_camera_module(
        monkeypatch, chunks=[b""]
    )

    camera = camera_module.CameraManager()
    assert camera.get_frame() is None


def test_camera_restarts_process_when_stream_ends(monkeypatch):
    camera_module, proc, popen_calls, _decoded = _load_camera_module(
        monkeypatch, chunks=[b""]
    )

    camera = camera_module.CameraManager()
    assert camera.get_frame() is None
    assert proc.terminated is True
    assert len(popen_calls) >= 2


def test_camera_get_frame_resets_large_raw_buffer(monkeypatch):
    large_chunk = b"a" * 2_100_000
    camera_module, _proc, _popen_calls, _decoded = _load_camera_module(
        monkeypatch, chunks=[large_chunk, b""]
    )

    camera = camera_module.CameraManager()
    assert camera.get_frame() is None
    assert camera.raw_bytes == b""


def test_camera_release_terminate_and_wait(monkeypatch):
    camera_module, proc, _popen_calls, _decoded = _load_camera_module(
        monkeypatch, chunks=[]
    )

    camera = camera_module.CameraManager()
    camera.release()

    assert proc.terminated is True
    assert proc.wait_called is True
    assert proc.killed is False
    assert camera.proc is None


def test_camera_release_kills_on_wait_timeout(monkeypatch):
    camera_module, proc, _popen_calls, _decoded = _load_camera_module(
        monkeypatch, chunks=[], wait_timeout=True
    )

    camera = camera_module.CameraManager()
    camera.release()

    assert proc.terminated is True
    assert proc.killed is True
    assert camera.proc is None
