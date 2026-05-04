from enum import Enum

from .mobile.ble_notifier import BleNotifier, MockBleNotifier


class SoundType(Enum):
    SUCCESS = "success"
    WARNING = "warning"


class DisplayC:
    def __init__(self):
        self.isScreenOn = True

    def showCategory(self, icon, text):
        print(f"[Display] 화면에 {icon} 아이콘 / 텍스트 '{text}' 표시")
        self.refreshScreen()

    def showWarning(self, message):
        print(f"[Display] 경고: {message}")
        self.refreshScreen()

    def refreshScreen(self):
        print("[Display] 화면 갱신")

    def show_category(self, text):
        self.showCategory(text, text)

    def show_warning(self, msg):
        self.showWarning(msg)


class AudioC:
    def __init__(self):
        self.volume = 5

    def playTTS(self, koreanText):
        print(f"[Audio] '이것은 {koreanText}입니다' 재생")

    def playEffect(self, soundType: SoundType):
        print(f"[Audio] 효과음 재생: {soundType.value}")

    def loadAudioFile(self, path):
        print(f"[Audio] 오디오 파일 로드 시도: {path}")
        return bool(path)

    def play_tts(self, text):
        self.playTTS(text)


class MotorC:
    def __init__(self, pinNumber=18):
        self.currentAngle = 0
        self.pinNumber = pinNumber

    def resetPosition(self):
        self.rotateTo(0)

    def rotateTo(self, angle):
        self.currentAngle = angle
        self.sendPWM(angle)
        print(f"[Motor] {angle}도로 회전하여 분류")

    def sendPWM(self, pulseWidth):
        print(f"[Motor] PWM 전송: pin={self.pinNumber}, pulse={pulseWidth}")

    def rotate_to(self, angle):
        self.rotateTo(angle)


class SensorC:
    def __init__(self, fillThreshold=0.8):
        self.fillThreshold = fillThreshold

    def checkFillLevel(self):
        analog = self.readAnalogValue()
        return max(0.0, min(1.0, analog / 1023.0))

    def isFull(self):
        return self.checkFillLevel() >= self.fillThreshold

    def readAnalogValue(self):
        return 0

    def is_full(self):
        return self.isFull()


class BluetoothC:
    def __init__(self, notifier: BleNotifier | None = None):
        self.isConnected = False
        self.notifier = notifier or MockBleNotifier()

    def connect(self):
        self.isConnected = True
        return self.isConnected

    def _notify_event(self, event, message):
        if not self.isConnected:
            self.connect()
        return self.notifier.notify(event, message)

    def sendAlert(self, message):
        return self._notify_event("BIN_FULL", message)

    def sendExceptionAlert(self, message):
        return self._notify_event("OUTPUT_EXCEPTION", message)

    def send_alert(self, msg):
        return self.sendAlert(msg)

    def send_exception_alert(self, msg):
        return self.sendExceptionAlert(msg)


class MobileApp:
    def __init__(self):
        self.isBluetoothOn = True

    def receiveAlert(self, msg):
        print(f"[MobileApp] 알림 수신: {msg}")
        self.showNotification()

    def showNotification(self):
        print("[MobileApp] 알림 배너 표시")


# Diagram compatibility alias.
ServoC = MotorC
