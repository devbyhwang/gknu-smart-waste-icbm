import time
from typing import Any, Optional, Tuple

from ultralytics import YOLO

from models import ClassificationResult, HandleClassificationResult, WasteType

LABEL_ALIASES = {
    "can": "can",
    "plastic": "plastic",
    "glass": "glass",
    "paper": "paper",
    "unknown": "unknown",
    "캔": "can",
    "금속캔": "can",
    "건전지": "can",
    "페트병": "plastic",
    "플라스틱": "plastic",
    "유리병": "glass",
    "형광등": "glass",
    "종이": "paper",
}


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
        max_count: int = 1,
        interval_ms: int = 1000,
        min_confidence: float = 0.6,
        handler: Optional[HandleClassificationResult] = None,
        img_dir: Optional[str] = None,
        camera_mgr=None,
    ):
        self.camera = camera if camera is not None else camera_mgr
        self.engine = engine
        self.handler = handler
        self.max_count = max_count
        self.interval_ms = interval_ms
        self.min_confidence = min_confidence
        self.img_dir = img_dir
        self.last_label = None
        self.consecutive_count = 0
        self._sensor_refresh_interval_sec = 5.0
        self._next_sensor_refresh_at = 0.0

    def _normalize_label(self, label: Optional[str]) -> Optional[str]:
        if label is None:
            return None
        normalized = str(label).strip()
        if not normalized:
            return None
        return LABEL_ALIASES.get(normalized.lower(), LABEL_ALIASES.get(normalized, normalized.lower()))

    def validate(self, label: Optional[str], conf: float) -> bool:
        label = self._normalize_label(label)
        if not label or conf < self.min_confidence:
            self.consecutive_count = 0
            return False

        if label == self.last_label:
            self.consecutive_count += 1
        else:
            self.last_label = label
            self.consecutive_count = 1

        return self.consecutive_count == self.max_count

    def map_to_enum(self, label_str: Optional[str]) -> WasteType:
        label_str = self._normalize_label(label_str)
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

    def _inference_interval_seconds(self) -> float:
        return max(0.0, self.interval_ms / 1000.0)

    def _refresh_sensor_snapshot_if_due(self, now: float):
        if now < self._next_sensor_refresh_at:
            return

        self._next_sensor_refresh_at = now + self._sensor_refresh_interval_sec
        if not self.handler:
            return

        refresh = getattr(self.handler, "refreshSensorStatus", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                # 센서 갱신 실패가 인식 루프를 멈추지 않도록 무시.
                pass

    def _draw_camera_overlay(
        self,
        frame,
        label: Optional[str],
        conf: float,
        bbox: Optional[Tuple[int, int, int, int]],
        triggered: bool,
        decision: str,
        last_pass_text: str,
        cycle: int,
    ):
        import cv2

        view = frame.copy()
        if bbox:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(view, (x1, y1), (x2, y2), (0, 255, 0), 2)

        detected_text = f"Detected: {label or 'none'} ({conf:.2f})"
        count_text = f"Consecutive: {self.consecutive_count}/{self.max_count}"
        trigger_text = "TRIGGERED" if triggered else "WAITING"
        quit_text = "Press 'q' or ESC to quit"
        rule_text = f"Rule: conf>={self.min_confidence:.2f} and same label x{self.max_count}"
        interval_text = f"Interval: {self.interval_ms}ms"
        cycle_text = f"Cycle: {cycle}"
        decision_text = f"Decision: {decision}"
        pass_text = f"Last pass: {last_pass_text}"

        cv2.putText(view, "[LIVE]", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
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
        cv2.putText(view, rule_text, (12, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(view, interval_text, (12, 154), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(view, cycle_text, (12, 178), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(view, decision_text, (12, 202), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(view, pass_text, (12, 226), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        cv2.putText(view, quit_text, (12, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
        return view

    def run(self, window_name: str = "EcoSort Monitor"):
        import cv2

        print("시스템 가동... (종료: q 또는 ESC)")
        next_inference_at = 0.0
        cycle = 0
        last_pass_text = "never"
        label = None
        conf = 0.0
        bbox = None
        triggered = False
        decision = "WAIT"
        try:
            while True:
                frame = self.camera.get_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue

                cycle += 1
                now = time.monotonic()
                self._refresh_sensor_snapshot_if_due(now)
                if now >= next_inference_at:
                    next_inference_at = now + self._inference_interval_seconds()
                    before_label = self.last_label
                    label, conf, bbox = self.engine.predict_detailed(frame)
                    normalized_label = self._normalize_label(label)
                    is_valid = self.validate(normalized_label, conf)
                    triggered = False
                    decision = "WAIT"

                    if not normalized_label:
                        decision = "NO_LABEL"
                    elif conf < self.min_confidence:
                        decision = "LOW_CONF"
                    elif normalized_label != before_label:
                        decision = "NEW_LABEL"
                    else:
                        decision = "COUNTING"

                    if is_valid:
                        triggered = True
                        decision = "PASSED"
                        last_pass_text = time.strftime("%H:%M:%S")
                        result = ClassificationResult(
                            label=self.map_to_enum(normalized_label),
                            confidence=conf,
                        )
                        self._dispatch_result(result)

                view = self._draw_camera_overlay(
                    frame=frame,
                    label=self._normalize_label(label),
                    conf=conf,
                    bbox=bbox,
                    triggered=triggered,
                    decision=decision,
                    last_pass_text=last_pass_text,
                    cycle=cycle,
                )
                cv2.imshow(window_name, view)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
        finally:
            cv2.destroyAllWindows()
            self.camera.release()
