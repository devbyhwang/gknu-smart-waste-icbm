import importlib
import sys
import types


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


def test_validate_threshold_and_reset(monkeypatch):
    inference_module = _load_inference_with_fake_ultralytics(monkeypatch)
    classifier = inference_module.WasteClassifier(
        camera_mgr=None,
        engine=None,
        handler=None,
        max_count=3,
    )

    assert classifier.validate("can", 0.9) is False
    assert classifier.consecutive_count == 1

    assert classifier.validate("can", 0.5) is False
    assert classifier.consecutive_count == 0


def test_validate_success_after_consecutive_count(monkeypatch):
    inference_module = _load_inference_with_fake_ultralytics(monkeypatch)
    classifier = inference_module.WasteClassifier(
        camera_mgr=None,
        engine=None,
        handler=None,
        max_count=3,
    )

    assert classifier.validate("plastic", 0.95) is False
    assert classifier.validate("plastic", 0.96) is False
    assert classifier.validate("plastic", 0.97) is True


def test_map_to_enum(monkeypatch):
    inference_module = _load_inference_with_fake_ultralytics(monkeypatch)
    classifier = inference_module.WasteClassifier(
        camera_mgr=None,
        engine=None,
        handler=None,
    )

    assert classifier.map_to_enum("can") == inference_module.WasteType.CAN
    assert classifier.map_to_enum("glass") == inference_module.WasteType.GLASS
    assert classifier.map_to_enum("new_type") == inference_module.WasteType.UNKNOWN


def test_handler_dispatch_prefers_camel_case(monkeypatch):
    inference_module = _load_inference_with_fake_ultralytics(monkeypatch)
    classifier = inference_module.WasteClassifier(camera_mgr=None, engine=None)

    class CamelHandler:
        def __init__(self):
            self.calls = []

        def handleClassification(self, result):
            self.calls.append(("camel", result.label))

        def handle_classification(self, result):
            self.calls.append(("snake", result.label))

    handler = CamelHandler()
    classifier.handler = handler
    result = inference_module.ClassificationResult(inference_module.WasteType.CAN, 0.88)
    classifier._dispatch_result(result)
    assert handler.calls == [("camel", inference_module.WasteType.CAN)]


def test_init_camera_parameter_compatibility(monkeypatch):
    inference_module = _load_inference_with_fake_ultralytics(monkeypatch)
    camera_obj = object()
    classifier = inference_module.WasteClassifier(camera=camera_obj, camera_mgr=None, engine=None)
    assert classifier.camera is camera_obj
