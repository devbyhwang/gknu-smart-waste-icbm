import json
from datetime import datetime

from src.hardware import BluetoothC
from src.mobile.ble_notifier import JsonPayloadBuilder, MockBleNotifier


def test_json_payload_builder_schema_and_timestamp():
    builder = JsonPayloadBuilder()
    payload = builder.build("BIN_FULL", "분류함 비움 필요")
    decoded = json.loads(payload.decode("utf-8"))

    assert decoded["event"] == "BIN_FULL"
    assert decoded["message"] == "분류함 비움 필요"
    assert "ts" in decoded
    assert isinstance(decoded["ts"], str)
    datetime.fromisoformat(decoded["ts"])


def test_mock_ble_notifier_records_notifications():
    notifier = MockBleNotifier()

    ok = notifier.notify("OUTPUT_EXCEPTION", "출력 장치 처리 중 예외가 발생했습니다.")

    assert ok is True
    assert len(notifier.notifications) == 1
    recorded = notifier.notifications[0]
    assert recorded.event == "OUTPUT_EXCEPTION"
    assert recorded.message == "출력 장치 처리 중 예외가 발생했습니다."

    decoded = json.loads(recorded.payload.decode("utf-8"))
    assert decoded["event"] == "OUTPUT_EXCEPTION"
    assert decoded["message"] == "출력 장치 처리 중 예외가 발생했습니다."


def test_bluetooth_alias_send_alert_routes_event():
    notifier = MockBleNotifier()
    bt = BluetoothC(notifier=notifier)

    ok = bt.send_alert("분류함 비움 필요")

    assert ok is True
    assert bt.isConnected is True
    assert len(notifier.notifications) == 1
    assert notifier.notifications[0].event == "BIN_FULL"
    assert notifier.notifications[0].message == "분류함 비움 필요"


def test_bluetooth_send_exception_alert_routes_event():
    notifier = MockBleNotifier()
    bt = BluetoothC(notifier=notifier)

    ok = bt.sendExceptionAlert("출력 장치 처리 중 예외가 발생했습니다.")

    assert ok is True
    assert bt.isConnected is True
    assert len(notifier.notifications) == 1
    assert notifier.notifications[0].event == "OUTPUT_EXCEPTION"
