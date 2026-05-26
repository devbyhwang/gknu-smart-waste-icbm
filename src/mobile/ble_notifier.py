import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List


@dataclass
class BleNotification:
    event: str
    message: str
    payload: bytes


class JsonPayloadBuilder:
    def build(self, event: str, message: str) -> bytes:
        payload = {
            "event": event,
            "message": message,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class BleNotifier(ABC):
    @abstractmethod
    def notify(self, event: str, message: str) -> bool:
        raise NotImplementedError


class PiBleNotifyTransport:
    """
    Production hook for Raspberry Pi BLE notify transport.
    Actual BlueZ integration is intentionally deferred.
    """

    def send(self, _payload: bytes) -> bool:
        return False


class MockBleNotifier(BleNotifier):
    def __init__(self, payload_builder: JsonPayloadBuilder | None = None):
        self.payload_builder = payload_builder or JsonPayloadBuilder()
        self.notifications: List[BleNotification] = []

    def notify(self, event: str, message: str) -> bool:
        payload = self.payload_builder.build(event, message)
        self.notifications.append(
            BleNotification(event=event, message=message, payload=payload)
        )
        return True


class PiBleNotifier(BleNotifier):
    def __init__(
        self,
        transport: PiBleNotifyTransport | None = None,
        payload_builder: JsonPayloadBuilder | None = None,
    ):
        self.transport = transport or PiBleNotifyTransport()
        self.payload_builder = payload_builder or JsonPayloadBuilder()

    def notify(self, event: str, message: str) -> bool:
        payload = self.payload_builder.build(event, message)
        return self.transport.send(payload)
