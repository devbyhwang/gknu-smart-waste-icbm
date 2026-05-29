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
SENSOR_REFRESH_INTERVAL_SECONDS = 0.5


class OutputM(HandleClassificationResult):
    def __init__(self):
        self.display = DisplayC()
        self.audio = AudioC()
        self.servo = ServoC()
        self.sensors = {
            waste_type: SensorC(**pin_config)
            for waste_type, pin_config in BIN_SENSOR_CONFIG.items()
        }
        self.sensor = self.sensors[WasteType.CAN]
        self.bluetooth = BluetoothC()
        self._display_lock = threading.RLock()
        self._sensor_update_stop = threading.Event()
        self._sensor_update_thread = None

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

    def _read_sensor_fill_level(self, sensor):
        reader = getattr(sensor, "checkFillLevel", None)
        if not callable(reader):
            return None

        try:
            value = reader()
        except Exception:
            return None

        if isinstance(value, (list, tuple)):
            return [self._clamp_fill_level(item) for item in value]

        return self._clamp_fill_level(value)

    def _clamp_fill_level(self, value):
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
                value = reader()
            except Exception:
                return None
            if isinstance(value, (list, tuple)):
                return [bool(item) for item in value]
            return bool(value)
        return None

    def _coerce_sequence_by_bin(self, values):
        if not isinstance(values, (list, tuple)):
            return None
        return {
            waste_type: values[index] if index < len(values) else None
            for index, waste_type in enumerate(BIN_SENSOR_CONFIG)
        }

    def _status_indicates_full(self, status):
        if isinstance(status, (list, tuple)):
            return any(bool(item) for item in status)
        return bool(status)

    def collectFillLevels(self):
        multi_sensor_levels = self._coerce_sequence_by_bin(
            self._read_sensor_fill_level(getattr(self, "sensor", None))
        )
        if multi_sensor_levels is not None:
            return multi_sensor_levels

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

        multi_sensor_status = self._coerce_sequence_by_bin(
            self._read_sensor_full_status(getattr(self, "sensor", None))
        )
        if multi_sensor_status is not None:
            for waste_type, is_full in multi_sensor_status.items():
                if is_full:
                    full_bins.add(waste_type)
            return full_bins

        for waste_type, sensor in getattr(self, "sensors", {}).items():
            if self._status_indicates_full(self._read_sensor_full_status(sensor)):
                full_bins.add(waste_type)
        return full_bins

    def checkBinFull(self, label=None, fill_levels=None):
        if self._status_indicates_full(self._read_sensor_full_status(getattr(self, "sensor", None))):
            return True

        full_bins = self.collectFullBins(fill_levels)
        if label is not None and label in full_bins:
            return True
        if full_bins:
            return True

        return False

    def refreshSensorDisplay(self):
        fill_levels = self.collectFillLevels()
        full_bins = self.collectFullBins(fill_levels)

        with self._display_lock:
            show_sensor_status = getattr(self.display, "showSensorStatus", None)
            if callable(show_sensor_status):
                show_sensor_status(fill_levels=fill_levels, full_bins=full_bins)
                return fill_levels, full_bins

            show_status = getattr(self.display, "showClassificationStatus", None)
            if callable(show_status):
                show_status(
                    None,
                    fill_levels=fill_levels,
                    full_bins=full_bins,
                    message="분류함 상태",
                )
                return fill_levels, full_bins

            refresh_screen = getattr(self.display, "refreshScreen", None)
            if callable(refresh_screen):
                refresh_screen()

        return fill_levels, full_bins

    def startSensorDisplayUpdates(self, interval_seconds=SENSOR_REFRESH_INTERVAL_SECONDS):
        if self._sensor_update_thread and self._sensor_update_thread.is_alive():
            return self._sensor_update_thread

        self._sensor_update_stop.clear()
        interval_seconds = max(0.1, float(interval_seconds))

        def _run():
            while not self._sensor_update_stop.is_set():
                try:
                    self.refreshSensorDisplay()
                except Exception:
                    pass
                self._sensor_update_stop.wait(interval_seconds)

        self._sensor_update_thread = threading.Thread(
            target=_run,
            name="smart-bin-sensor-display",
            daemon=True,
        )
        self._sensor_update_thread.start()
        return self._sensor_update_thread

    def stopSensorDisplayUpdates(self, timeout=1.0):
        self._sensor_update_stop.set()
        thread = self._sensor_update_thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

    def _show_bin_full_warning(self, result, fill_levels, full_bins):
        show_bin_full = getattr(self.display, "showBinFullWarning", None)
        if callable(show_bin_full):
            with self._display_lock:
                show_bin_full(BIN_FULL_WARNING, fill_levels=fill_levels, full_bins=full_bins)
            return

        show_status = getattr(self.display, "showClassificationStatus", None)
        if callable(show_status):
            with self._display_lock:
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
            with self._display_lock:
                show_warning(BIN_FULL_WARNING)
            return

        legacy_warning = getattr(self.display, "show_warning", None)
        if callable(legacy_warning):
            with self._display_lock:
                legacy_warning(BIN_FULL_WARNING)

    def _block_classification_for_full_bin(self, result, fill_levels, full_bins):
        self._show_bin_full_warning(result, fill_levels, full_bins)

        play_effect = getattr(self.audio, "playEffect", None)
        if callable(play_effect):
            play_effect(SoundType.WARNING)

        self._send_bluetooth_event(
            "BIN_FULL",
            BIN_FULL_ALERT,
            "sendAlert",
            "send_alert",
        )

    def handleException(self):
        warning_text = "출력 장치 처리 중 예외가 발생했습니다."
        show_warning = getattr(self.display, "showWarning", None)
        if callable(show_warning):
            with self._display_lock:
                show_warning(warning_text)
        else:
            legacy_warning = getattr(self.display, "show_warning", None)
            if callable(legacy_warning):
                with self._display_lock:
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
            fill_levels = self.collectFillLevels()
            full_bins = self.collectFullBins(fill_levels)
            if self._status_indicates_full(self._read_sensor_full_status(getattr(self, "sensor", None))):
                full_bins.add(result.label)

            if full_bins:
                print(f"[OutputM] 분류 중단: 가득 찬 분류함={', '.join(item.value for item in full_bins)}")
                self._block_classification_for_full_bin(result, fill_levels, full_bins)
                return

            show_status = getattr(self.display, "showClassificationStatus", None)
            if callable(show_status):
                with self._display_lock:
                    show_status(
                        result.label,
                        confidence=result.confidence,
                        fill_levels=fill_levels,
                        full_bins=full_bins,
                    )
            else:
                show_category = getattr(self.display, "showCategory", None)
                if callable(show_category):
                    with self._display_lock:
                        show_category(result.label.value, result.label.value)
                else:
                    legacy_show_category = getattr(self.display, "show_category", None)
                    if callable(legacy_show_category):
                        with self._display_lock:
                            legacy_show_category(result.label.value)

            play_tts = getattr(self.audio, "playTTS", None)
            if callable(play_tts):
                play_tts(result.label.value)
            else:
                legacy_play_tts = getattr(self.audio, "play_tts", None)
                if callable(legacy_play_tts):
                    legacy_play_tts(result.label.value)

            process_item = getattr(self.servo, "process_item", None)
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
        except Exception:
            self.handleException()

    def handle_classification(self, result: ClassificationResult):
        return self.handleClassification(result)


class OutputManager(OutputM):
    pass
