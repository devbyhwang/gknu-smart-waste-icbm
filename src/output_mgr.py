import threading

from hardware import AudioC, BluetoothC, DisplayC, MotorC, SensorC, SoundType
from models import ClassificationResult, HandleClassificationResult, WasteType


BIN_SENSOR_CONFIG = {
    # 각 분류함에 연결된 초음파 센서 GPIO 핀 번호.
    WasteType.CAN: {"trig": 23, "echo": 25},
    WasteType.PLASTIC: {"trig": 17, "echo": 27},
    WasteType.GLASS: {"trig": 22, "echo": 24},
    WasteType.PAPER: {"trig": 5, "echo": 6},
}

BIN_FULL_WARNING = "분류함이 가득 찼습니다! 비운 후 다시 시도하세요."
BIN_FULL_ALERT = "분류함 비움 필요"


class OutputM(HandleClassificationResult):
    def __init__(self):
        # 분류 결과를 화면, 음성, 모터, 센서, BLE 장치로 전달하는 중앙 관리자.
        self.display = DisplayC()
        self.audio = AudioC()
        self.servo = MotorC()
        self.sensors = {
            waste_type: SensorC(**pin_config)
            for waste_type, pin_config in BIN_SENSOR_CONFIG.items()
        }
        self.sensor = self.sensors[WasteType.CAN]
        self.bluetooth = BluetoothC()
        self._state_lock = threading.RLock()
        self._alerted_full_bins = set()
        self._motor_active = False
        self._last_fill_levels = {}
        self._last_full_bins = set()

    def _send_bluetooth_event(self, event: str, message: str):
        try:
            return bool(self.bluetooth.sendEvent(event, message))
        except Exception:
            return False

    def _bin_full_alert_message(self, full_bins):
        if not full_bins:
            return BIN_FULL_ALERT

        names = ", ".join(sorted(waste_type.value for waste_type in full_bins))
        return f"{names} 분류함 비움 필요"

    def _send_new_full_bin_alert(self, full_bins):
        # 이미 알린 분류함은 반복 알림을 보내지 않는다.
        current_full_bins = set(full_bins or set())
        newly_full_bins = current_full_bins - self._alerted_full_bins

        if not newly_full_bins:
            self._alerted_full_bins &= current_full_bins
            return False

        message = self._bin_full_alert_message(newly_full_bins)
        print(f"[OutputM] 새 가득참 BLE 알림: {message}")

        sent = self._send_bluetooth_event("BIN_FULL", message)

        self._alerted_full_bins |= newly_full_bins
        self._alerted_full_bins &= current_full_bins
        print(f"[OutputM] BLE BIN_FULL 전송 결과: {sent}")
        return sent

    def _read_sensor_fill_level(self, sensor):
        # 센서 읽기 실패는 None으로 처리해서 전체 출력 흐름을 막지 않는다.
        if sensor is None:
            return None

        try:
            value = sensor.checkFillLevel()
        except Exception:
            return None

        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return None

    def _read_sensor_full_status(self, sensor):
        if sensor is None:
            return None

        try:
            return bool(sensor.isFull())
        except Exception:
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
        # 채움 비율이 각 센서 임계값 이상이면 가득 찬 분류함으로 본다.
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

    def _show_bin_full_warning(self, result, fill_levels, full_bins):
        self.display.showBinFullWarning(BIN_FULL_WARNING, fill_levels=fill_levels, full_bins=full_bins)

    def _show_sensor_snapshot(self, fill_levels, full_bins):
        self.display.showSensorSnapshot(fill_levels=fill_levels, full_bins=full_bins, message="인식 대기")

    def refreshSensorStatus(self):
        with self._state_lock:
            # 모터가 움직이는 중에는 센서값이 흔들릴 수 있어 마지막 값을 유지한다.
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

    def _block_classification_for_full_bin(self, result, fill_levels, full_bins):
        # 분류함이 가득 차면 모터를 움직이지 않고 경고만 보낸다.
        self._show_bin_full_warning(result, fill_levels, full_bins)

        play_effect = getattr(self.audio, "playEffect", None)
        if callable(play_effect):
            play_effect(SoundType.WARNING)

        self._send_new_full_bin_alert(full_bins)

    def handleException(self):
        # 출력 장치 중 하나가 실패해도 사용자에게 경고하고 루프는 계속 살린다.
        warning_text = "출력 장치 처리 중 예외가 발생했습니다."
        with self._state_lock:
            self.display.showWarning(warning_text)

        self.audio.playEffect(SoundType.WARNING)

        self._send_bluetooth_event("OUTPUT_EXCEPTION", warning_text)

    def handleClassification(self, result: ClassificationResult):
        try:
            print(f"\n[OutputM] 결과 처리 시작: {result.label.value}")
            with self._state_lock:
                # 모터 동작 전에 최신 센서 상태를 확인해 넘침을 방지한다.
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

                self.display.showClassificationStatus(
                    result.label,
                    confidence=result.confidence,
                    fill_levels=fill_levels,
                    full_bins=full_bins,
                )

            self.audio.play_tts(result.label.value)

            self._set_motor_active(True)
            try:
                # 실제 분류 동작 중에는 센서 polling이 끼어들지 않도록 표시한다.
                self.servo.process_item(result.label.value)
            finally:
                self._set_motor_active(False)
        except Exception:
            self.handleException()
