import asyncio
import inspect
import json
import threading
from datetime import datetime, timezone
from typing import Optional

from bless import (
    BlessServer,
    GATTAttributePermissions,
    GATTCharacteristicProperties,
)


DEVICE_NAME = "RaspberryPi_BLE"
SERVICE_UUID = "f82d9a22-3dc9-430e-875d-583c9ced1904"
CHAR_UUID = "2c5bba85-ac1c-46c2-a8d3-db389101a028"


def build_payload(event: str, message: str) -> bytes:
    # 스마트폰 앱이 바로 파싱할 수 있도록 이벤트, 메시지, UTC 시간을 JSON으로 묶는다.
    payload = {
        "event": event,
        "message": message,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


async def maybe_await(value):
    # bless 버전에 따라 동기/비동기 반환이 섞일 수 있어 둘 다 처리한다.
    if inspect.isawaitable(value):
        return await value
    return value


async def get_connected(server) -> bool:
    attr = server.is_connected
    if callable(attr):
        result = attr()
        result = await maybe_await(result)
        return bool(result)
    return bool(attr)


class PiBleNotifyTransport:
    def __init__(self, service_uuid: str = SERVICE_UUID, char_uuid: str = CHAR_UUID):
        self.service_uuid = service_uuid
        self.char_uuid = char_uuid
        self.server = None

    def set_server(self, server):
        self.server = server

    async def send(self, payload: bytes) -> bool:
        # BLE notify는 클라이언트가 연결되고 characteristic을 구독해야 성공한다.
        if self.server is None:
            print("[BLE] server is None")
            return False

        try:
            connected = await get_connected(self.server)
            if not connected:
                print("[BLE] 아직 BLE 클라이언트가 연결되지 않음")
                return False

            char = self.server.get_characteristic(self.char_uuid)
            if char is None:
                print("[BLE] characteristic not found")
                return False

            char.value = bytearray(payload)
            ok = await maybe_await(
                self.server.update_value(self.service_uuid, self.char_uuid)
            )
            print(f"[BLE] connected={connected}, update_value={ok}")

            if not ok:
                print("[BLE] update_value=False (클라이언트 구독/CCCD 미설정 가능)")
                return False

            return True
        except Exception as exc:
            print(f"[BLE] 전송 에러: {exc}")
            return False


class PiBleNotifier:
    def __init__(self, transport: PiBleNotifyTransport):
        self.transport = transport

    async def notify(self, event: str, message: str) -> bool:
        return await self.transport.send(build_payload(event, message))


class EmbeddedBleServer:
    def __init__(
        self,
        name: str = DEVICE_NAME,
        service_uuid: str = SERVICE_UUID,
        char_uuid: str = CHAR_UUID,
    ):
        self.name = name
        self.service_uuid = service_uuid
        self.char_uuid = char_uuid
        self.transport = PiBleNotifyTransport(service_uuid, char_uuid)
        self.notifier = PiBleNotifier(self.transport)
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.server = None
        self._started_event = threading.Event()
        self._start_error: Optional[BaseException] = None

    @property
    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive() and self.server is not None

    def start(self, timeout: float = 5.0) -> bool:
        # BLE 이벤트 루프는 메인 분류 루프를 막지 않도록 별도 스레드에서 실행한다.
        if self.is_running:
            return True

        self._started_event.clear()
        self._start_error = None
        self.thread = threading.Thread(target=self._run_loop, name="PiBleServer", daemon=True)
        self.thread.start()

        if not self._started_event.wait(timeout):
            print("[BLE] 서버 시작 시간 초과")
            return False

        if self._start_error is not None:
            print(f"[BLE] 서버 시작 실패: {self._start_error}")
            return False

        return self.is_running

    def send_event(self, event: str, message: str) -> bool:
        # 다른 스레드에서 BLE 루프에 안전하게 notify 작업을 등록한다.
        if not self.is_running or self.loop is None:
            return False

        future = asyncio.run_coroutine_threadsafe(
            self.notifier.notify(event, message),
            self.loop,
        )
        try:
            return bool(future.result(timeout=3.0))
        except Exception as exc:
            print(f"[BLE] notify 실패: {exc}")
            return False

    def stop(self):
        if self.loop is not None and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

    def _run_loop(self):
        # 스레드 내부 전용 asyncio loop를 만들고 서버 생명주기를 관리한다.
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._start_server())
            self._started_event.set()
            self.loop.run_forever()
        except BaseException as exc:
            self._start_error = exc
            self._started_event.set()
        finally:
            self.loop.run_until_complete(self._stop_server())
            self.loop.close()

    async def _start_server(self):
        # 하나의 서비스와 notify 가능한 characteristic으로 단순한 알림 채널을 만든다.
        if BlessServer is None:
            raise RuntimeError("bless 패키지가 설치되어 있지 않습니다.")
        if GATTCharacteristicProperties is None or GATTAttributePermissions is None:
            raise RuntimeError("bless GATT 타입을 사용할 수 없습니다.")

        self.server = BlessServer(name=self.name)
        await self.server.add_new_service(self.service_uuid)
        await self.server.add_new_characteristic(
            self.service_uuid,
            self.char_uuid,
            GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
            bytearray(b"{}"),
            GATTAttributePermissions.readable,
        )
        self.transport.set_server(self.server)
        await self.server.start()
        print("[BLE] 서버 시작")
        print(f"[BLE] Name: {self.name}")
        print(f"[BLE] Service UUID: {self.service_uuid}")
        print(f"[BLE] Char UUID: {self.char_uuid}")

    async def _stop_server(self):
        if self.server is None:
            return
        try:
            await maybe_await(self.server.stop())
        finally:
            self.server = None
            self.transport.set_server(None)
