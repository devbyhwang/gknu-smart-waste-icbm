import asyncio
import json

from src.ble_notify import (
    CHAR_UUID,
    SERVICE_UUID,
    PiBleNotifyTransport,
    build_payload,
    get_connected,
)


def test_build_payload_contains_event_message_and_timestamp():
    payload = json.loads(build_payload("BIN_FULL", "분류함 비움 필요").decode("utf-8"))

    assert payload["event"] == "BIN_FULL"
    assert payload["message"] == "분류함 비움 필요"
    assert payload["ts"].endswith("+00:00")


def test_get_connected_handles_property_sync_method_and_async_method():
    class PropertyServer:
        is_connected = True

    class MethodServer:
        def is_connected(self):
            return True

    class AsyncMethodServer:
        async def is_connected(self):
            return True

    assert asyncio.run(get_connected(PropertyServer())) is True
    assert asyncio.run(get_connected(MethodServer())) is True
    assert asyncio.run(get_connected(AsyncMethodServer())) is True


def test_transport_send_false_without_server():
    transport = PiBleNotifyTransport()

    assert asyncio.run(transport.send(b"{}")) is False


def test_transport_send_false_when_not_connected():
    class Server:
        is_connected = False

    transport = PiBleNotifyTransport()
    transport.set_server(Server())

    assert asyncio.run(transport.send(b"{}")) is False


def test_transport_send_false_when_characteristic_missing():
    class Server:
        is_connected = True

        def get_characteristic(self, _uuid):
            return None

    transport = PiBleNotifyTransport()
    transport.set_server(Server())

    assert asyncio.run(transport.send(b"{}")) is False


def test_transport_send_false_when_update_value_false():
    class Characteristic:
        value = bytearray()

    class Server:
        is_connected = True

        def __init__(self):
            self.char = Characteristic()

        def get_characteristic(self, _uuid):
            return self.char

        def update_value(self, service_uuid, char_uuid):
            assert service_uuid == SERVICE_UUID
            assert char_uuid == CHAR_UUID
            return False

    transport = PiBleNotifyTransport()
    transport.set_server(Server())

    assert asyncio.run(transport.send(b"{}")) is False


def test_transport_send_success_sets_characteristic_value():
    class Characteristic:
        value = bytearray()

    class Server:
        is_connected = True

        def __init__(self):
            self.char = Characteristic()

        def get_characteristic(self, _uuid):
            return self.char

        async def update_value(self, service_uuid, char_uuid):
            assert service_uuid == SERVICE_UUID
            assert char_uuid == CHAR_UUID
            return True

    server = Server()
    transport = PiBleNotifyTransport()
    transport.set_server(server)

    assert asyncio.run(transport.send(b'{"event":"BIN_FULL"}')) is True
    assert server.char.value == bytearray(b'{"event":"BIN_FULL"}')
