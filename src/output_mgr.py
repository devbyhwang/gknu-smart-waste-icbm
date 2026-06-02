import threading

try:
    from .hardware import AudioC, BluetoothC, DisplayC, SensorC, ServoC, SoundType
    from .models import ClassificationResult, HandleClassificationResult, WasteType
except ImportError:
    from hardware import AudioC, BluetoothC, DisplayC, SensorC, ServoC, SoundType
    from models import ClassificationResult, HandleClassificationResult, WasteType


BIN_SENSOR_CONFIG = {
    WasteType.CAN: {"trig": 23, "echo": 25},
    WasteType.PLASTIC: {"trig": 17, "echo": 27},
    WasteType.GLASS: {"trig": 22, "echo": 24},
    WasteType.PAPER: {"trig": 5, "echo": 6},
}

BIN_FULL_WARNING = "분류함이 가득 찼습니다! 비운 후 다시 시도하세요."
BIN_FULL_ALERT = "분류함 비움 필요"


class OutputM(HandleClassificationResult):
    def __init__(self, sensor_refresh_interval_sec: float = 5.0, enable_sensor_polling: bool = False):
        self.display = DisplayC()
        self.audio = AudioC()
        self.servo = ServoC()
        self.sensors = {
            waste_type: SensorC(**pin_config)
            for waste_type, pin_config in BIN_SENSOR_CONFIG.items()
        }
        self.sensor = self.sensors[WasteType.CAN]
        self.bluetooth = BluetoothC()
        self.sensor_refresh_interval_sec = max(0.5, float(sensor_refresh_interval_sec))
        self._state_lock = threading.RLock()
        self._polling_stop = threading.Event()
        self._polling_thread = None
        self._alerted_full_bins = set()
        self._motor_active = False
        self._last_fill_levels = {}
        self._last_full_bins = set()

        if enable_sensor_polling:
            self.start_sensor_polling()

    def _send_bluetooth_message(self, method_name: str, legacy_name: str, message: str):
        sender = getattr(self.bluetooth, method_name, None)
        if not callable(sender):
            sender = getattr(self.bluetooth, legacy_name, None)
        if not callable(sender):
            return False

        try:
            sender(message)
            return True
        except Exception:
            return False

    def _send_bluetooth_event(self, event: str, message: str, method_name: str, legacy_name: str):
        sender = getattr(self.bluetooth, "sendEvent", None)
        if callable(sender):
            try:
                return bool(sender(event, message))
            except Exception:
                return False

        return self._send_bluetooth_message(method_name, legacy_name, message)

    def _bin_full_alert_message(self, full_bins):
        if not full_bins:
            return BIN_FULL_ALERT

        names = ", ".join(sorted(waste_type.value for waste_type in full_bins))
        return f"{names} 분류함 비움 필요"

    def _send_new_full_bin_alert(self, full_bins):
        current_full_bins = set(full_bins or set())
        newly_full_bins = current_full_bins - self._alerted_full_bins

        if not newly_full_bins:
            self._alerted_full_bins &= current_full_bins
            return False

        message = self._bin_full_alert_message(newly_full_bins)
        print(f"[OutputM] 새 가득참 BLE 알림: {message}")

        sent = self._send_bluetooth_event(
            "BIN_FULL",
            message,
            "sendAlert",
            "send_alert",
        )

        self._alerted_full_bins |= newly_full_bins
        self._alerted_full_bins &= current_full_bins
        print(f"[OutputM] BLE BIN_FULL 전송 결과: {sent}")
        return sent

    def _read_sensor_fill_level(self, sensor):
        reader = getattr(sensor, "checkFillLevel", None)
        if not callable(reader):
            return None

        try:
            value = reader()
        except Exception:
            return None

        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return None

    def _read_sensor_full_status(self, sensor):
        for method_name in ("isFull", "is_full"):
            reader = getattr(sensor, method_name, None)
            if not callable(reader):
                continue
            try:
                return bool(reader())
            except Exception:
                return None
        return None

    def collectFillLevels(self):
        fill_levels = {}
        for waste_type, sensor in getattr(self, "sensors", {}).items():
            fill_levels[waste_type] = self._read_sensor_fill_level(sensor)
        return fill_levels

    def _sensor_threshold(self, waste_type):
        sensor = getattr(self, "sensors", {}).get(waste_type)
        try:
            return float(getattr(sensor, "fillThreshold", 0.8))
        except (TypeError, ValueError):
            return 0.8

    def _full_bins_from_fill_levels(self, fill_levels):
        full_bins = set()
        for waste_type, fill_level in (fill_levels or {}).items():
            if fill_level is not None and fill_level >= self._sensor_threshold(waste_type):
                full_bins.add(waste_type)
        return full_bins

    def collectFullBins(self, fill_levels=None):
        full_bins = self._full_bins_from_fill_levels(fill_levels)
        for waste_type, sensor in getattr(self, "sensors", {}).items():
            if self._read_sensor_full_status(sensor):
                full_bins.add(waste_type)
        return full_bins

    def checkBinFull(self, label=None, fill_levels=None):
        if self._read_sensor_full_status(getattr(self, "sensor", None)):
            return True

        full_bins = self.collectFullBins(fill_levels)
        if label is not None and label in full_bins:
            return True
        if full_bins:
            return True

        return False

    def _show_bin_full_warning(self, result, fill_levels, full_bins):
        show_bin_full = getattr(self.display, "showBinFullWarning", None)
        if callable(show_bin_full):
            show_bin_full(BIN_FULL_WARNING, fill_levels=fill_levels, full_bins=full_bins)
            return

        show_status = getattr(self.display, "showClassificationStatus", None)
        if callable(show_status):
            try:
                show_status(
                    result.label,
                    confidence=result.confidence,
                    fill_levels=fill_levels,
                    full_bins=full_bins,
                    message=BIN_FULL_WARNING,
                )
            except TypeError:
                show_status(
                    result.label,
                    confidence=result.confidence,
                    fill_levels=fill_levels,
                    full_bins=full_bins,
                )

        show_warning = getattr(self.display, "showWarning", None)
        if callable(show_warning):
            show_warning(BIN_FULL_WARNING)
            return

        legacy_warning = getattr(self.display, "show_warning", None)
        if callable(legacy_warning):
            legacy_warning(BIN_FULL_WARNING)

    def _show_sensor_snapshot(self, fill_levels, full_bins):
        show_snapshot = getattr(self.display, "showSensorSnapshot", None)
        if callable(show_snapshot):
            show_snapshot(fill_levels=fill_levels, full_bins=full_bins, message="인식 대기")
            return

        show_status = getattr(self.display, "showClassificationStatus", None)
        if callable(show_status):
            try:
                show_status(
                    WasteType.UNKNOWN,
                    confidence=None,
                    fill_levels=fill_levels,
                    full_bins=full_bins,
                    message="인식 대기",
                )
            except TypeError:
                show_status(
                    WasteType.UNKNOWN,
                    confidence=None,
                    fill_levels=fill_levels,
                    full_bins=full_bins,
                )

    def refreshSensorStatus(self):
        with self._state_lock:
            if self._motor_active:
                return dict(self._last_fill_levels), set(self._last_full_bins)

            fill_levels = self.collectFillLevels()
            full_bins = self.collectFullBins(fill_levels)
            self._last_fill_levels = dict(fill_levels)
            self._last_full_bins = set(full_bins)
            self._show_sensor_snapshot(fill_levels, full_bins)
            self._send_new_full_bin_alert(full_bins)
            return fill_levels, full_bins

    def _set_motor_active(self, active: bool):
        with self._state_lock:
            self._motor_active = bool(active)

    def _sensor_polling_loop(self):
        while not self._polling_stop.is_set():
            try:
                self.refreshSensorStatus()
            except Exception:
                # 백그라운드 갱신 실패가 전체 분류 루프를 중단시키지 않도록 무시.
                pass

            if self._polling_stop.wait(self.sensor_refresh_interval_sec):
                break

    def start_sensor_polling(self):
        if self._polling_thread is not None and self._polling_thread.is_alive():
            return False

        self._polling_stop.clear()
        self._polling_thread = threading.Thread(
            target=self._sensor_polling_loop,
            name="SensorDisplayPoller",
            daemon=True,
        )
        self._polling_thread.start()
        return True

    def stop_sensor_polling(self, join_timeout_sec: float = 1.0):
        self._polling_stop.set()
        thread = self._polling_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(join_timeout_sec)))
        self._polling_thread = None

    def _block_classification_for_full_bin(self, result, fill_levels, full_bins):
        self._show_bin_full_warning(result, fill_levels, full_bins)

        play_effect = getattr(self.audio, "playEffect", None)
        if callable(play_effect):
            play_effect(SoundType.WARNING)

        self._send_new_full_bin_alert(full_bins)

    def handleException(self):
        warning_text = "출력 장치 처리 중 예외가 발생했습니다."
        with self._state_lock:
            show_warning = getattr(self.display, "showWarning", None)
            if callable(show_warning):
                show_warning(warning_text)
            else:
                legacy_warning = getattr(self.display, "show_warning", None)
                if callable(legacy_warning):
                    legacy_warning(warning_text)

        play_effect = getattr(self.audio, "playEffect", None)
        if callable(play_effect):
            play_effect(SoundType.WARNING)

        self._send_bluetooth_event(
            "OUTPUT_EXCEPTION",
            warning_text,
            "sendExceptionAlert",
            "send_exception_alert",
        )

    def handleClassification(self, result: ClassificationResult):
        try:
            print(f"\n[OutputM] 결과 처리 시작: {result.label.value}")
            with self._state_lock:
                fill_levels = self.collectFillLevels()
                full_bins = self.collectFullBins(fill_levels)
                if self._read_sensor_full_status(getattr(self, "sensor", None)):
                    full_bins.add(result.label)

                self._last_fill_levels = dict(fill_levels)
                self._last_full_bins = set(full_bins)

                if full_bins:
                    print(f"[OutputM] 분류 중단: 가득 찬 분류함={', '.join(item.value for item in full_bins)}")
                    self._block_classification_for_full_bin(result, fill_levels, full_bins)
                    return

                show_status = getattr(self.display, "showClassificationStatus", None)
                if callable(show_status):
                    show_status(
                        result.label,
                        confidence=result.confidence,
                        fill_levels=fill_levels,
                        full_bins=full_bins,
                    )
                else:
                    show_category = getattr(self.display, "showCategory", None)
                    if callable(show_category):
                        show_category(result.label.value, result.label.value)
                    else:
                        legacy_show_category = getattr(self.display, "show_category", None)
                        if callable(legacy_show_category):
                            legacy_show_category(result.label.value)

            play_tts = getattr(self.audio, "playTTS", None)
            if callable(play_tts):
                play_tts(result.label.value)
            else:
                legacy_play_tts = getattr(self.audio, "play_tts", None)
                if callable(legacy_play_tts):
                    legacy_play_tts(result.label.value)

            process_item = getattr(self.servo, "process_item", None)
            self._set_motor_active(True)
            try:
                if callable(process_item):
                    process_item(result.label.value)
                else:
                    rotate_to = getattr(self.servo, "rotateTo", None)
                    if callable(rotate_to):
                        rotate_to(90)
                    else:
                        legacy_rotate_to = getattr(self.servo, "rotate_to", None)
                        if callable(legacy_rotate_to):
                            legacy_rotate_to(90)
            finally:
                self._set_motor_active(False)
        except Exception:
            self.handleException()

    def handle_classification(self, result: ClassificationResult):
        return self.handleClassification(result)


class OutputManager(OutputM):
    pass
