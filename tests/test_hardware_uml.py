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


def test_motor_and_servo_alias():
    motor = MotorC(pinNumber=12)
    motor.rotateTo(90)
    assert motor.currentAngle == 90
    motor.resetPosition()
    assert motor.currentAngle == 0
    assert ServoC is MotorC


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
