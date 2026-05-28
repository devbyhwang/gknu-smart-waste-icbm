import importlib
import sys
import types

import pytest


def _load_inference_with_fake_ultralytics(monkeypatch):
    class DummyYOLO:
        def __init__(self, _model_path):
            self.names = {0: "can"}

        def predict(self, _frame, verbose=False):
            return []

    fake_ultralytics = types.SimpleNamespace(YOLO=DummyYOLO)
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)
    sys.modules.pop("src.inference", None)
    return importlib.import_module("src.inference")


class _StopLoop(Exception):
    """Test-only exception used to stop the classifier loop deterministically."""


class _ScriptedCamera:
    def __init__(self, frames):
        self.frames = list(frames)
        self.released = False

    def get_frame(self):
        frame = self.frames.pop(0)
        if isinstance(frame, BaseException):
            raise frame
        return frame

    def release(self):
        self.released = True


def test_pipeline_e2e_success_with_fake_components(monkeypatch):
    inference_module = _load_inference_with_fake_ultralytics(monkeypatch)
    monkeypatch.setattr(inference_module.time, "sleep", lambda _s: None)

    class Engine:
        def predict(self, _frame):
            return "can", 0.95

    class Handler:
        def __init__(self):
            self.calls = []

        def handleClassification(self, result):
            self.calls.append((result.label.value, result.confidence))

    camera = _ScriptedCamera([None, "frame-1", _StopLoop()])
    handler = Handler()
    classifier = inference_module.WasteClassifier(
        camera=camera,
        engine=Engine(),
        max_count=1,
        interval_ms=0,
        handler=handler,
    )

    with pytest.raises(_StopLoop):
        classifier.run()

    assert handler.calls == [("Can", 0.95)]
    assert camera.released is True


def test_pipeline_e2e_failure_routes_to_handle_exception(monkeypatch):
    inference_module = _load_inference_with_fake_ultralytics(monkeypatch)
    monkeypatch.setattr(inference_module.time, "sleep", lambda _s: None)

    from src.output_mgr import OutputM

    class Engine:
        def predict(self, _frame):
            return "can", 0.96

    class SafeDisplay:
        def __init__(self):
            self.warning_calls = 0

        def showCategory(self, _icon, _text):
            return None

        def showWarning(self, _message):
            self.warning_calls += 1

    class SafeAudio:
        def __init__(self):
            self.effect_calls = 0

        def playTTS(self, _text):
            return None

        def playEffect(self, _sound_type):
            self.effect_calls += 1

    class BrokenMotor:
        def rotateTo(self, _angle):
            raise RuntimeError("motor failure")

    class NotFullSensor:
        def isFull(self):
            return False

    class NoopBluetooth:
        def sendAlert(self, _msg):
            return None

    output = OutputM()
    output.display = SafeDisplay()
    output.audio = SafeAudio()
    output.servo = BrokenMotor()
    output.sensor = NotFullSensor()
    output.bluetooth = NoopBluetooth()

    camera = _ScriptedCamera(["frame-1", _StopLoop()])
    classifier = inference_module.WasteClassifier(
        camera=camera,
        engine=Engine(),
        max_count=1,
        interval_ms=0,
        handler=output,
    )

    with pytest.raises(_StopLoop):
        classifier.run()

    assert camera.released is True
    assert output.display.warning_calls == 1
    assert output.audio.effect_calls == 1


def test_pipeline_reads_frames_continuously_and_throttles_yolo(monkeypatch):
    inference_module = _load_inference_with_fake_ultralytics(monkeypatch)
    monotonic_values = iter([0.0, 0.05, 0.10, 0.21])
    monkeypatch.setattr(inference_module.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(inference_module.time, "sleep", lambda _s: None)

    class Engine:
        def __init__(self):
            self.calls = []

        def predict(self, frame):
            self.calls.append(frame)
            return "can", 0.95

    class Handler:
        def __init__(self):
            self.calls = []

        def handleClassification(self, result):
            self.calls.append((result.label.value, result.confidence))

    camera = _ScriptedCamera(["frame-1", "frame-2", "frame-3", "frame-4", _StopLoop()])
    engine = Engine()
    handler = Handler()
    classifier = inference_module.WasteClassifier(
        camera=camera,
        engine=engine,
        max_count=1,
        interval_ms=200,
        handler=handler,
    )

    with pytest.raises(_StopLoop):
        classifier.run()

    assert engine.calls == ["frame-1", "frame-4"]
    assert handler.calls == [("Can", 0.95)]
    assert camera.released is True
