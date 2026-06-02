from src.models import ClassificationResult, WasteType
from src.output_mgr import BIN_FULL_WARNING, BIN_SENSOR_CONFIG, OutputM, OutputManager


class StubDisplay:
    def __init__(self):
        self.calls = []

    def show_category(self, text):
        self.calls.append(("show_category", text))

    def show_warning(self, msg):
        self.calls.append(("show_warning", msg))


class StubAudio:
    def __init__(self):
        self.calls = []

    def play_tts(self, text):
        self.calls.append(("play_tts", text))


class StubMotor:
    def __init__(self):
        self.calls = []

    def rotate_to(self, angle):
        self.calls.append(("rotate_to", angle))


class ProcessMotor:
    def __init__(self):
        self.calls = []

    def process_item(self, received_value):
        self.calls.append(("process_item", received_value))


class StubSensor:
    def __init__(self, full):
        self.full = full

    def is_full(self):
        return self.full


class StubBluetooth:
    def __init__(self):
        self.calls = []

    def send_alert(self, msg):
        self.calls.append(("send_alert", msg))

    def send_exception_alert(self, msg):
        self.calls.append(("send_exception_alert", msg))


def test_bin_sensor_config_matches_physical_gpio_layout():
    assert BIN_SENSOR_CONFIG == {
        WasteType.CAN: {"trig": 23, "echo": 25},
        WasteType.PLASTIC: {"trig": 17, "echo": 27},
        WasteType.GLASS: {"trig": 22, "echo": 24},
        WasteType.PAPER: {"trig": 5, "echo": 6},
    }


def test_output_manager_sequence_without_full_bin():
    output = OutputManager()
    output.display = StubDisplay()
    output.audio = StubAudio()
    output.servo = StubMotor()
    output.sensor = StubSensor(full=False)
    output.bluetooth = StubBluetooth()

    output.handle_classification(ClassificationResult(WasteType.CAN, 0.85))

    assert output.display.calls == [("show_category", "Can")]
    assert output.audio.calls == [("play_tts", "Can")]
    assert output.servo.calls == [("rotate_to", 90)]
    assert output.bluetooth.calls == []


def test_outputm_uses_process_item_before_legacy_rotate_methods():
    output = OutputManager()
    output.display = StubDisplay()
    output.audio = StubAudio()
    output.servo = ProcessMotor()
    output.sensor = StubSensor(full=False)
    output.bluetooth = StubBluetooth()

    output.handle_classification(ClassificationResult(WasteType.PLASTIC, 0.85))

    assert output.servo.calls == [("process_item", "Plastic")]


def test_output_manager_full_bin_branch():
    output = OutputManager()
    output.display = StubDisplay()
    output.audio = StubAudio()
    output.servo = StubMotor()
    output.sensor = StubSensor(full=True)
    output.bluetooth = StubBluetooth()

    output.handle_classification(ClassificationResult(WasteType.PAPER, 0.90))

    assert output.display.calls == [("show_warning", BIN_FULL_WARNING)]
    assert output.audio.calls == []
    assert output.servo.calls == []
    assert output.bluetooth.calls == [("send_alert", "Paper 분류함 비움 필요")]


def test_outputm_camel_case_path():
    class CamelDisplay:
        def __init__(self):
            self.calls = []

        def showCategory(self, icon, text):
            self.calls.append(("showCategory", icon, text))

        def showWarning(self, message):
            self.calls.append(("showWarning", message))

    class CamelAudio:
        def __init__(self):
            self.calls = []

        def playTTS(self, text):
            self.calls.append(("playTTS", text))

    class CamelMotor:
        def __init__(self):
            self.calls = []

        def rotateTo(self, angle):
            self.calls.append(("rotateTo", angle))

    class CamelSensor:
        def __init__(self, full):
            self.full = full

        def isFull(self):
            return self.full

    class CamelBluetooth:
        def __init__(self):
            self.calls = []

        def sendAlert(self, message):
            self.calls.append(("sendAlert", message))

    output = OutputM()
    output.display = CamelDisplay()
    output.audio = CamelAudio()
    output.servo = CamelMotor()
    output.sensor = CamelSensor(full=True)
    output.bluetooth = CamelBluetooth()

    output.handleClassification(ClassificationResult(WasteType.GLASS, 0.95))

    assert output.display.calls == [("showWarning", BIN_FULL_WARNING)]
    assert output.audio.calls == []
    assert output.servo.calls == []
    assert output.bluetooth.calls == [("sendAlert", "Glass 분류함 비움 필요")]


def test_output_manager_is_compat_alias():
    output = OutputManager()
    assert isinstance(output, OutputM)


def test_outputm_routes_device_exception_to_handle_exception():
    class SafeDisplay:
        def __init__(self):
            self.calls = []

        def showCategory(self, icon, text):
            self.calls.append(("showCategory", icon, text))

        def showWarning(self, message):
            self.calls.append(("showWarning", message))

    class SafeAudio:
        def __init__(self):
            self.calls = []

        def playTTS(self, text):
            self.calls.append(("playTTS", text))

        def playEffect(self, sound_type):
            self.calls.append(("playEffect", sound_type.value))

    class BrokenMotor:
        def rotateTo(self, _angle):
            raise RuntimeError("servo failed")

    class NotFullSensor:
        def isFull(self):
            return False

    class EventBluetooth:
        def __init__(self):
            self.calls = []

        def sendExceptionAlert(self, message):
            self.calls.append(("sendExceptionAlert", message))

    output = OutputM()
    output.display = SafeDisplay()
    output.audio = SafeAudio()
    output.servo = BrokenMotor()
    output.sensor = NotFullSensor()
    output.bluetooth = EventBluetooth()

    output.handleClassification(ClassificationResult(WasteType.CAN, 0.92))

    assert ("showCategory", "Can", "Can") in output.display.calls
    assert ("showWarning", "출력 장치 처리 중 예외가 발생했습니다.") in output.display.calls
    assert ("playEffect", "warning") in output.audio.calls
    assert output.bluetooth.calls == [
        ("sendExceptionAlert", "출력 장치 처리 중 예외가 발생했습니다."),
    ]


def test_outputm_routes_process_item_exception_to_handle_exception():
    class SafeDisplay:
        def __init__(self):
            self.calls = []

        def showCategory(self, icon, text):
            self.calls.append(("showCategory", icon, text))

        def showWarning(self, message):
            self.calls.append(("showWarning", message))

    class SafeAudio:
        def __init__(self):
            self.calls = []

        def playTTS(self, text):
            self.calls.append(("playTTS", text))

        def playEffect(self, sound_type):
            self.calls.append(("playEffect", sound_type.value))

    class BrokenProcessMotor:
        def process_item(self, _received_value):
            raise RuntimeError("servo failed")

    class NotFullSensor:
        def isFull(self):
            return False

    class EventBluetooth:
        def __init__(self):
            self.calls = []

        def sendExceptionAlert(self, message):
            self.calls.append(("sendExceptionAlert", message))

    output = OutputM()
    output.display = SafeDisplay()
    output.audio = SafeAudio()
    output.servo = BrokenProcessMotor()
    output.sensor = NotFullSensor()
    output.bluetooth = EventBluetooth()

    output.handleClassification(ClassificationResult(WasteType.PLASTIC, 0.92))

    assert ("showCategory", "Plastic", "Plastic") in output.display.calls
    assert ("showWarning", "출력 장치 처리 중 예외가 발생했습니다.") in output.display.calls
    assert ("playEffect", "warning") in output.audio.calls
    assert output.bluetooth.calls == [
        ("sendExceptionAlert", "출력 장치 처리 중 예외가 발생했습니다."),
    ]


def test_outputm_full_bin_uses_typed_ble_event():
    class EventBluetooth:
        def __init__(self):
            self.calls = []

        def sendEvent(self, event, message):
            self.calls.append((event, message))
            return True

    output = OutputM()
    output.display = StubDisplay()
    output.audio = StubAudio()
    output.servo = StubMotor()
    output.sensor = StubSensor(full=True)
    output.bluetooth = EventBluetooth()

    output.handleClassification(ClassificationResult(WasteType.CAN, 0.91))

    assert output.bluetooth.calls == [("BIN_FULL", "Can 분류함 비움 필요")]


def test_outputm_passes_four_sensor_levels_to_display_status():
    class StatusDisplay:
        def __init__(self):
            self.calls = []

        def showClassificationStatus(self, label, confidence=None, fill_levels=None, full_bins=None):
            self.calls.append((label, confidence, fill_levels, full_bins))

        def showWarning(self, message):
            self.calls.append(("warning", message))

    class FillSensor:
        def __init__(self, value, threshold=0.8):
            self.value = value
            self.fillThreshold = threshold

        def checkFillLevel(self):
            if isinstance(self.value, Exception):
                raise self.value
            return self.value

        def isFull(self):
            return False

    class EventBluetooth:
        def __init__(self):
            self.calls = []

        def sendEvent(self, event, message):
            self.calls.append((event, message))
            return True

    output = OutputM()
    output.display = StatusDisplay()
    output.audio = StubAudio()
    output.servo = StubMotor()
    output.sensor = FillSensor(0.0)
    output.sensors = {
        WasteType.CAN: FillSensor(0.10),
        WasteType.PLASTIC: FillSensor(0.82),
        WasteType.GLASS: FillSensor(RuntimeError("sensor down")),
        WasteType.PAPER: FillSensor(1.2),
    }
    output.bluetooth = EventBluetooth()

    output.handleClassification(ClassificationResult(WasteType.PLASTIC, 0.90))

    label, confidence, fill_levels, full_bins = output.display.calls[0]
    assert label is WasteType.PLASTIC
    assert confidence == 0.90
    assert fill_levels == {
        WasteType.CAN: 0.10,
        WasteType.PLASTIC: 0.82,
        WasteType.GLASS: None,
        WasteType.PAPER: 1.0,
    }
    assert full_bins == {WasteType.PLASTIC, WasteType.PAPER}
    assert ("warning", BIN_FULL_WARNING) in output.display.calls
    assert output.audio.calls == []
    assert output.servo.calls == []
    assert output.bluetooth.calls == [("BIN_FULL", "Paper, Plastic 분류함 비움 필요")]


def test_outputm_alerts_when_any_sensor_reports_full_without_fill_level():
    class StatusDisplay:
        def __init__(self):
            self.calls = []

        def showClassificationStatus(self, label, confidence=None, fill_levels=None, full_bins=None):
            self.calls.append((label, confidence, fill_levels, full_bins))

        def showWarning(self, message):
            self.calls.append(("warning", message))

    class FullOnlySensor:
        def __init__(self, full):
            self.full = full

        def isFull(self):
            return self.full

    class EventBluetooth:
        def __init__(self):
            self.calls = []

        def sendEvent(self, event, message):
            self.calls.append((event, message))
            return True

    output = OutputM()
    output.display = StatusDisplay()
    output.audio = StubAudio()
    output.servo = StubMotor()
    output.sensor = FullOnlySensor(False)
    output.sensors = {
        WasteType.CAN: FullOnlySensor(False),
        WasteType.PLASTIC: FullOnlySensor(True),
        WasteType.GLASS: FullOnlySensor(False),
        WasteType.PAPER: FullOnlySensor(False),
    }
    output.bluetooth = EventBluetooth()

    output.handleClassification(ClassificationResult(WasteType.CAN, 0.90))

    _label, _confidence, _fill_levels, full_bins = output.display.calls[0]
    assert full_bins == {WasteType.PLASTIC}
    assert ("warning", BIN_FULL_WARNING) in output.display.calls
    assert output.audio.calls == []
    assert output.servo.calls == []
    assert output.bluetooth.calls == [("BIN_FULL", "Plastic 분류함 비움 필요")]


def test_outputm_exception_uses_output_exception_ble_event():
    class SafeDisplay:
        def showWarning(self, _message):
            return None

    class SafeAudio:
        def playEffect(self, _sound_type):
            return None

    class EventBluetooth:
        def __init__(self):
            self.calls = []

        def sendEvent(self, event, message):
            self.calls.append((event, message))
            return True

    output = OutputM()
    output.display = SafeDisplay()
    output.audio = SafeAudio()
    output.bluetooth = EventBluetooth()

    output.handleException()

    assert output.bluetooth.calls == [
        ("OUTPUT_EXCEPTION", "출력 장치 처리 중 예외가 발생했습니다."),
    ]


def test_outputm_ble_failure_does_not_break_exception_flow():
    class SafeDisplay:
        def __init__(self):
            self.calls = []

        def showWarning(self, message):
            self.calls.append(("showWarning", message))

    class SafeAudio:
        def __init__(self):
            self.calls = []

        def playEffect(self, sound_type):
            self.calls.append(("playEffect", sound_type.value))

    class BrokenBluetooth:
        def sendExceptionAlert(self, _message):
            raise RuntimeError("ble down")

    output = OutputM()
    output.display = SafeDisplay()
    output.audio = SafeAudio()
    output.bluetooth = BrokenBluetooth()

    output.handleException()

    assert ("showWarning", "출력 장치 처리 중 예외가 발생했습니다.") in output.display.calls
    assert ("playEffect", "warning") in output.audio.calls


def test_outputm_refresh_sensor_status_updates_four_bins():
    class SnapshotDisplay:
        def __init__(self):
            self.calls = []

        def showSensorSnapshot(self, fill_levels=None, full_bins=None, message=None):
            self.calls.append((fill_levels, full_bins, message))

    class FillSensor:
        def __init__(self, value, threshold=0.8):
            self.value = value
            self.fillThreshold = threshold

        def checkFillLevel(self):
            return self.value

        def isFull(self):
            return self.value >= self.fillThreshold

    class EventBluetooth:
        def __init__(self):
            self.calls = []

        def sendEvent(self, event, message):
            self.calls.append((event, message))
            return True

    output = OutputM()
    output.display = SnapshotDisplay()
    output.bluetooth = EventBluetooth()
    output.sensors = {
        WasteType.CAN: FillSensor(0.10),
        WasteType.PLASTIC: FillSensor(0.40),
        WasteType.GLASS: FillSensor(0.85),
        WasteType.PAPER: FillSensor(0.95),
    }

    fill_levels, full_bins = output.refreshSensorStatus()

    assert fill_levels == {
        WasteType.CAN: 0.10,
        WasteType.PLASTIC: 0.40,
        WasteType.GLASS: 0.85,
        WasteType.PAPER: 0.95,
    }
    assert full_bins == {WasteType.GLASS, WasteType.PAPER}
    assert output.display.calls == [(fill_levels, full_bins, "인식 대기")]
    assert output.bluetooth.calls == [("BIN_FULL", "Glass, Paper 분류함 비움 필요")]


def test_outputm_refresh_sensor_status_sends_ble_once_per_full_transition():
    class SnapshotDisplay:
        def showSensorSnapshot(self, fill_levels=None, full_bins=None, message=None):
            return None

    class FillSensor:
        fillThreshold = 0.8

        def __init__(self, value):
            self.value = value

        def checkFillLevel(self):
            return self.value

        def isFull(self):
            return self.value >= self.fillThreshold

    class EventBluetooth:
        def __init__(self):
            self.calls = []

        def sendEvent(self, event, message):
            self.calls.append((event, message))
            return True

    can_sensor = FillSensor(0.90)
    output = OutputM()
    output.display = SnapshotDisplay()
    output.bluetooth = EventBluetooth()
    output.sensors = {
        WasteType.CAN: can_sensor,
        WasteType.PLASTIC: FillSensor(0.10),
        WasteType.GLASS: FillSensor(0.10),
        WasteType.PAPER: FillSensor(0.10),
    }

    output.refreshSensorStatus()
    output.refreshSensorStatus()
    can_sensor.value = 0.20
    output.refreshSensorStatus()
    can_sensor.value = 0.95
    output.refreshSensorStatus()

    assert output.bluetooth.calls == [
        ("BIN_FULL", "Can 분류함 비움 필요"),
        ("BIN_FULL", "Can 분류함 비움 필요"),
    ]


def test_outputm_ignores_sensor_refresh_while_motor_is_sorting():
    class SnapshotDisplay:
        def __init__(self):
            self.calls = []

        def showClassificationStatus(self, label, confidence=None, fill_levels=None, full_bins=None):
            self.calls.append(("classification", label, confidence, fill_levels, full_bins))

        def showSensorSnapshot(self, fill_levels=None, full_bins=None, message=None):
            self.calls.append(("snapshot", fill_levels, full_bins, message))

    class FillSensor:
        fillThreshold = 0.8

        def __init__(self, value):
            self.value = value

        def checkFillLevel(self):
            return self.value

        def isFull(self):
            return self.value >= self.fillThreshold

    class EventBluetooth:
        def __init__(self):
            self.calls = []

        def sendEvent(self, event, message):
            self.calls.append((event, message))
            return True

    class RefreshingMotor:
        def __init__(self, output, can_sensor):
            self.output = output
            self.can_sensor = can_sensor
            self.calls = []

        def process_item(self, received_value):
            self.calls.append(("process_item", received_value))
            self.can_sensor.value = 0.95
            self.output.refreshSensorStatus()

    can_sensor = FillSensor(0.10)
    output = OutputM()
    output.display = SnapshotDisplay()
    output.audio = StubAudio()
    output.bluetooth = EventBluetooth()
    output.sensor = can_sensor
    output.sensors = {
        WasteType.CAN: can_sensor,
        WasteType.PLASTIC: FillSensor(0.10),
        WasteType.GLASS: FillSensor(0.10),
        WasteType.PAPER: FillSensor(0.10),
    }
    output.servo = RefreshingMotor(output, can_sensor)

    output.handleClassification(ClassificationResult(WasteType.CAN, 0.91))

    assert output.servo.calls == [("process_item", "Can")]
    assert output.display.calls == [
        (
            "classification",
            WasteType.CAN,
            0.91,
            {
                WasteType.CAN: 0.10,
                WasteType.PLASTIC: 0.10,
                WasteType.GLASS: 0.10,
                WasteType.PAPER: 0.10,
            },
            set(),
        ),
    ]
    assert output.bluetooth.calls == []


def test_outputm_sensor_polling_start_stop_is_idempotent():
    class SnapshotDisplay:
        def showSensorSnapshot(self, fill_levels=None, full_bins=None, message=None):
            return None

    output = OutputM(sensor_refresh_interval_sec=0.5)
    output.display = SnapshotDisplay()

    assert output.start_sensor_polling() is True
    assert output.start_sensor_polling() is False

    output.stop_sensor_polling()
    assert output._polling_thread is None
