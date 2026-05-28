from src.models import ClassificationResult, WasteType
from src.output_mgr import OutputM, OutputManager


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


def test_output_manager_full_bin_branch():
    output = OutputManager()
    output.display = StubDisplay()
    output.audio = StubAudio()
    output.servo = StubMotor()
    output.sensor = StubSensor(full=True)
    output.bluetooth = StubBluetooth()

    output.handle_classification(ClassificationResult(WasteType.PAPER, 0.90))

    assert ("show_category", "Paper") in output.display.calls
    assert ("show_warning", "분류함이 가득 찼습니다!") in output.display.calls
    assert output.audio.calls == [("play_tts", "Paper")]
    assert output.servo.calls == [("rotate_to", 90)]
    assert output.bluetooth.calls == [("send_alert", "분류함 비움 필요")]


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

    assert output.display.calls[0] == ("showCategory", "Glass", "Glass")
    assert ("showWarning", "분류함이 가득 찼습니다!") in output.display.calls
    assert output.audio.calls == [("playTTS", "Glass")]
    assert output.servo.calls == [("rotateTo", 90)]
    assert output.bluetooth.calls == [("sendAlert", "분류함 비움 필요")]


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

    assert output.bluetooth.calls == [("BIN_FULL", "분류함 비움 필요")]


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
    assert ("warning", "분류함이 가득 찼습니다!") in output.display.calls
    assert output.bluetooth.calls == [("BIN_FULL", "분류함 비움 필요")]


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
