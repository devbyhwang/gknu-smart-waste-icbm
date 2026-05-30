from pathlib import Path

from src.ble_notify import CHAR_UUID, SERVICE_UUID


DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "android-ble-notification-guide.md"


def test_android_ble_guide_uses_pi_gatt_uuids():
    guide = DOC_PATH.read_text(encoding="utf-8")

    assert f"Service UUID: `{SERVICE_UUID}`" in guide
    assert f"Notify Characteristic UUID: `{CHAR_UUID}`" in guide
    assert f'UUID.fromString("{SERVICE_UUID}")' in guide
    assert f'UUID.fromString("{CHAR_UUID}")' in guide
    assert "Pi -> Android notify only" in guide


def test_android_ble_guide_closes_stale_gatt_before_reconnect():
    guide = DOC_PATH.read_text(encoding="utf-8")

    assert "fun disconnect()" in guide
    assert "disconnect()" in guide.split("fun connect(device: BluetoothDevice)", 1)[1]
    assert "STATE_DISCONNECTED" in guide
    assert "Closing stale GATT" in guide
