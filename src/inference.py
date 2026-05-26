import time
from typing import Any, Optional, Tuple

from ultralytics import YOLO

try:
    from .models import ClassificationResult, HandleClassificationResult, WasteType
except ImportError:
    from models import ClassificationResult, HandleClassificationResult, WasteType


class InferenceEngine:
    def __init__(
        self,
        model_path: str,
        conf_thres: float = 0.1,
        imgsz: int = 320,
        device: str = "cpu",
    ):
        self.model = YOLO(model_path)
        self.conf_thres = conf_thres
        self.imgsz = imgsz
        self.device = device

    def predict(self, frame: Any):
        label, conf, _bbox = self.predict_detailed(frame)
        return label, conf

    def predict_detailed(self, frame: Any) -> Tuple[Optional[str], float, Optional[Tuple[int, int, int, int]]]:
        predict_kwargs = {
            "verbose": False,
            "conf": self.conf_thres,
            "imgsz": self.imgsz,
            "device": self.device,
        }
        try:
            res = self.model.predict(frame, **predict_kwargs)
        except TypeError:
            # Test doubles and older wrappers may only accept verbose.
            res = self.model.predict(frame, verbose=False)
        if res and len(res[0].boxes) > 0:
            boxes = res[0].boxes
            box = max(boxes, key=lambda b: b.conf.item())
            label = self.model.names[int(box.cls.item())]
            conf = float(box.conf.item())

            bbox = None
            if hasattr(box, "xyxy") and len(box.xyxy) > 0:
                coords = box.xyxy[0].tolist()
                x1, y1, x2, y2 = [int(max(0, c)) for c in coords]
                bbox = (x1, y1, x2, y2)

            return label, conf, bbox
        return None, 0.0, None


class WasteClassifier:
    def __init__(
        self,
        camera=None,
        engine: Optional[InferenceEngine] = None,
        max_count: int = 3,
        interval_ms: int = 1000,
        handler: Optional[HandleClassificationResult] = None,
        img_dir: Optional[str] = None,
        camera_mgr=None,
    ):
        self.camera = camera if camera is not None else camera_mgr
        self.engine = engine
        self.handler = handler
        self.max_count = max_count
        self.interval_ms = interval_ms
        self.img_dir = img_dir
        self.last_label = None
        self.consecutive_count = 0

    def validate(self, label: Optional[str], conf: float) -> bool:
        if not label or conf < 0.8:
            self.consecutive_count = 0
            return False

        if label == self.last_label:
            self.consecutive_count += 1
        else:
            self.last_label = label
            self.consecutive_count = 1

        return self.consecutive_count == self.max_count

    def map_to_enum(self, label_str: Optional[str]) -> WasteType:
        if not label_str:
            return WasteType.UNKNOWN

        mapping = {
            "can": WasteType.CAN,
            "plastic": WasteType.PLASTIC,
            "glass": WasteType.GLASS,
            "paper": WasteType.PAPER,
            "unknown": WasteType.UNKNOWN,
        }
        return mapping.get(label_str.lower(), WasteType.UNKNOWN)

    def _dispatch_result(self, result: ClassificationResult):
        if not self.handler:
            return

        # Prefer diagram-aligned camelCase API first.
        camel = getattr(self.handler, "handleClassification", None)
        if callable(camel):
            camel(result)
            return

        legacy = getattr(self.handler, "handle_classification", None)
        if callable(legacy):
            legacy(result)

    def run(self):
        print("시스템 가동...")
        try:
            while True:
                frame = self.camera.get_frame()
                if frame is None:
                    print("[Warning] 프레임을 읽지 못했습니다. 다시 시도합니다...")
                    time.sleep(0.1)
                    continue

                label, conf = self.engine.predict(frame)
                if self.validate(label, conf):
                    result = ClassificationResult(
                        label=self.map_to_enum(label),
                        confidence=conf,
                    )
                    self._dispatch_result(result)

                time.sleep(self.interval_ms / 1000.0)
        finally:
            self.camera.release()

    def run_test_mode(
        self,
        dispatch_results: bool = False,
        window_name: str = "EcoSort Test Monitor",
    ):
        import cv2

        print("테스트 모드 가동... (종료: q 또는 ESC)")
        cycle = 0
        last_pass_text = "never"
        try:
            while True:
                frame = self.camera.get_frame()
                if frame is None:
                    print("[Warning] 프레임을 읽지 못했습니다. 다시 시도합니다...")
                    time.sleep(0.1)
                    continue

                cycle += 1
                before_label = self.last_label
                label, conf, bbox = self.engine.predict_detailed(frame)
                is_valid = self.validate(label, conf)
                triggered = False
                decision = "WAIT"

                if not label:
                    decision = "NO_LABEL"
                elif conf < 0.8:
                    decision = "LOW_CONF"
                elif label != before_label:
                    decision = "NEW_LABEL"
                else:
                    decision = "COUNTING"

                if is_valid:
                    triggered = True
                    decision = "PASSED"
                    last_pass_text = time.strftime("%H:%M:%S")
                    if dispatch_results:
                        result = ClassificationResult(
                            label=self.map_to_enum(label),
                            confidence=conf,
                        )
                        self._dispatch_result(result)

                view = frame.copy()
                if bbox:
                    x1, y1, x2, y2 = bbox
                    cv2.rectangle(view, (x1, y1), (x2, y2), (0, 255, 0), 2)

                detected_text = f"Detected: {label or 'none'} ({conf:.2f})"
                count_text = f"Consecutive: {self.consecutive_count}/{self.max_count}"
                trigger_text = "TRIGGERED" if triggered else "WAITING"
                dispatch_text = "Dispatch: ON" if dispatch_results else "Dispatch: OFF"
                quit_text = "Press 'q' or ESC to quit"
                rule_text = f"Rule: conf>=0.80 and same label x{self.max_count}"
                interval_text = f"Interval: {self.interval_ms}ms"
                cycle_text = f"Cycle: {cycle}"
                decision_text = f"Decision: {decision}"
                pass_text = f"Last pass: {last_pass_text}"

                cv2.putText(view, "[TEST MODE]", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.putText(view, detected_text, (12, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(view, count_text, (12, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(
                    view,
                    trigger_text,
                    (12, 104),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0) if triggered else (0, 165, 255),
                    2,
                )
                cv2.putText(view, dispatch_text, (12, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
                cv2.putText(view, rule_text, (12, 156), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(view, interval_text, (12, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(view, cycle_text, (12, 204), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(view, decision_text, (12, 228), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(view, pass_text, (12, 252), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                cv2.putText(view, quit_text, (12, 276), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

                cv2.imshow(window_name, view)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break

                time.sleep(self.interval_ms / 1000.0)
        finally:
            cv2.destroyAllWindows()
            self.camera.release()
