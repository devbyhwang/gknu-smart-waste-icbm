import src.hardware as hardware
from src.hardware import BluetoothC, DisplayC, MobileApp, MotorC, SensorC, ServoC
from src.models import WasteType


def test_display_camel_and_snake_methods():
    display = DisplayC()
    display.showCategory("can", "Can")
    display.show_category("Can")
    display.showWarning("warn")
    display.show_warning("warn-legacy")
    assert display.isScreenOn is True


def test_display_renders_four_bin_fill_dashboard():
    display = DisplayC(enable_window=False)
    levels = {
        WasteType.CAN: 0.1,
        WasteType.PLASTIC: 0.45,
        WasteType.GLASS: 0.8,
        WasteType.PAPER: 1.0,
    }

    display.showClassificationStatus(
        WasteType.PLASTIC,
        confidence=0.91,
        fill_levels=levels,
        full_bins={WasteType.GLASS, WasteType.PAPER},
    )

    frame = display.render_frame()
    assert frame is not None
    assert frame.shape == (720, 1280, 3)
    assert display.selected_label == "Plastic"
    assert display.fill_levels["Can"] == 0.1
    assert display.fill_levels["Plastic"] == 0.45
    assert display.full_bins == {"Glass", "Paper"}


def test_display_clamps_bad_fill_values_without_breaking_render():
    display = DisplayC(enable_window=False)

    display.showClassificationStatus(
        "Can",
        confidence=0.5,
        fill_levels={"Can": 2, "Plastic": -1, "Glass": "bad", "Paper": None},
        full_bins={"Can"},
    )

    assert display.fill_levels["Can"] == 1.0
    assert display.fill_levels["Plastic"] == 0.0
    assert display.fill_levels["Glass"] is None
    assert display.fill_levels["Paper"] is None
    assert display.render_frame() is not None


def test_display_uses_only_korean_font_candidates_for_hangul_text():
    display = DisplayC(enable_window=False)

    candidates = list(display._font_candidates(display._contains_hangul("분류 결과 표시")))

    assert "/usr/share/fonts/truetype/nanum/NanumGothic.ttf" in candidates
    assert "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc" in candidates
    assert "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" not in candidates


def test_display_allows_dejavu_fallback_for_ascii_text():
    display = DisplayC(enable_window=False)

    candidates = list(display._font_candidates(display._contains_hangul("Display ready")))

    assert "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" in candidates


def test_motor_and_servo_alias():
    motor = MotorC(pinNumber=12)
    motor.rotateTo(90)
    assert motor.currentAngle == 90
    motor.resetPosition()
    assert motor.currentAngle == 0
    assert ServoC is MotorC


def test_motor_defaults_to_two_servo_pr23_configuration():
    motor = MotorC(move_delay=0)
    assert motor.bottom_pin == 18
    assert motor.top_pin == 19
    assert motor.bottom_angle == 0
    assert motor.top_angle == 90
    assert ServoC is MotorC


def test_motor_servo_starts_uncontrolled_and_detaches_after_reset(monkeypatch):
    created = []

    class FakeServo:
        def __init__(self, pin, **kwargs):
            self.pin = pin
            self.kwargs = kwargs
            self.angle = None
            self.detached = 0
            created.append(self)

        def detach(self):
            self.detached += 1

    monkeypatch.setattr(hardware, "AngularServo", FakeServo)
    monkeypatch.setattr(hardware, "_GPIO_FACTORY", object())

    motor = MotorC(move_delay=0)

    assert [servo.pin for servo in created] == [18, 19]
    assert [servo.kwargs["initial_angle"] for servo in created] == [None, None]
    assert created[0].angle == 0
    assert created[1].angle == 90
    assert [servo.detached for servo in created] == [1, 1]
    assert motor.command_log == [("bottom", 0), ("top", 90)]


def test_motor_process_item_uses_pr23_angle_map_and_resets():
    motor = MotorC(move_delay=0)
    motor.command_log.clear()

    motor.process_item("Plastic")

    assert motor.command_log == [
        ("bottom", 15),
        ("top", 135),
        ("bottom", 0),
        ("top", 90),
    ]
    assert motor.bottom_angle == 0
    assert motor.top_angle == 90
    assert motor.currentAngle == 0


def test_motor_process_item_unknown_uses_unknown_angle_map():
    motor = MotorC(move_delay=0)
    motor.command_log.clear()

    motor.process_item("Battery")

    assert motor.command_log[:2] == [("bottom", 90), ("top", 135)]
    assert motor.bottom_angle == 0
    assert motor.top_angle == 90


def test_sensor_fill_threshold_and_alias():
    sensor = SensorC(fillThreshold=0.8)
    assert sensor.fillThreshold == 0.8
    assert sensor.checkFillLevel() == 0.0
    assert sensor.isFull() is False
    assert sensor.is_full() is False


def test_bluetooth_connect_and_alert_alias():
    class FakeServer:
        def __init__(self):
            self.started = False
            self.events = []

        def start(self):
            self.started = True
            return True

        def send_event(self, event, message):
            self.events.append((event, message))
            return True

    server = FakeServer()
    bt = BluetoothC(server=server)
    assert bt.isConnected is False
    assert bt.connect() is True
    assert bt.sendAlert("msg") is True
    assert bt.send_alert("msg2") is True
    assert bt.isConnected is True
    assert server.events == [
        ("BIN_FULL", "msg"),
        ("BIN_FULL", "msg2"),
    ]


def test_mobile_app_stub_methods():
    app = MobileApp()
    assert app.isBluetoothOn is True
    app.receiveAlert("test")
    app.showNotification()
