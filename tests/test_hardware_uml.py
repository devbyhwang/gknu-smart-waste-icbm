from src.hardware import BluetoothC, DisplayC, MobileApp, MotorC, SensorC, ServoC


def test_display_camel_and_snake_methods():
    display = DisplayC()
    display.showCategory("can", "Can")
    display.show_category("Can")
    display.showWarning("warn")
    display.show_warning("warn-legacy")
    assert display.isScreenOn is True


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
