from enum import Enum
import glob
import os
import subprocess
import sys
from time import sleep

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

try:
    from .ble_notify import EmbeddedBleServer
    from .mobile.ble_notifier import BleNotifier, MockBleNotifier
except ImportError:
    from ble_notify import EmbeddedBleServer
    from mobile.ble_notifier import BleNotifier, MockBleNotifier

try:
    import pygame
except Exception:
    pygame = None

try:
    from gpiozero import AngularServo, DistanceSensor
    from gpiozero.pins.lgpio import LGPIOFactory

    _GPIO_FACTORY = LGPIOFactory()
except Exception:
    AngularServo = None
    DistanceSensor = None
    _GPIO_FACTORY = None


class SoundType(Enum):
    SUCCESS = "success"
    WARNING = "warning"


class DisplayC:
    BIN_ORDER = ("Can", "Plastic", "Glass", "Paper")
    IMAGE_BY_BIN = {
        "Can": "금속.PNG",
        "Plastic": "플라스틱.PNG",
        "Glass": "유리.PNG",
        "Paper": "종이.PNG",
    }
    WINDOW_NAME = "Smart Bin Display"

    def __init__(self, img_dir=None, window_name=None, enable_window=None):
        self.isScreenOn = True
        self.window_name = window_name or self.WINDOW_NAME
        self.img_dir = img_dir or self._default_img_dir()
        self.selected_label = None
        self.confidence = None
        self.fill_levels = {label: None for label in self.BIN_ORDER}
        self.full_bins = set()
        self.message = "인식 대기"
        self._asset_cache = {}
        self._font_cache = {}
        self._missing_korean_font_warned = False
        self._window_ready = False
        self.enable_window = self._should_enable_window(enable_window)

    def _default_img_dir(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "img"))

    def _should_enable_window(self, enable_window):
        if enable_window is not None:
            return bool(enable_window)
        if cv2 is None or os.environ.get("PYTEST_CURRENT_TEST"):
            return False
        if os.environ.get("SMART_BIN_DISPLAY_HEADLESS") == "1":
            return False
        if sys.platform == "darwin":
            return True
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    def _normalize_bin_key(self, key):
        if key is None:
            return None
        value = getattr(key, "value", key)
        value = str(value)
        aliases = {
            "can": "Can",
            "plastic": "Plastic",
            "glass": "Glass",
            "paper": "Paper",
            "캔": "Can",
            "금속": "Can",
            "금속캔": "Can",
            "페트병": "Plastic",
            "플라스틱": "Plastic",
            "유리": "Glass",
            "유리병": "Glass",
            "종이": "Paper",
        }
        return aliases.get(value.lower(), aliases.get(value, value if value in self.BIN_ORDER else None))

    def _normalize_fill_levels(self, fill_levels):
        normalized = {label: None for label in self.BIN_ORDER}
        if not fill_levels:
            return normalized
        for key, value in fill_levels.items():
            label = self._normalize_bin_key(key)
            if label not in normalized:
                continue
            if value is None:
                normalized[label] = None
                continue
            try:
                normalized[label] = max(0.0, min(1.0, float(value)))
            except (TypeError, ValueError):
                normalized[label] = None
        return normalized

    def _load_asset(self, label):
        if cv2 is None:
            return None
        if label in self._asset_cache:
            return self._asset_cache[label]

        filename = self.IMAGE_BY_BIN.get(label)
        path = os.path.join(self.img_dir, filename) if filename else None
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED) if path and os.path.exists(path) else None
        self._asset_cache[label] = image
        return image

    def _paste_image(self, canvas, image, x, y, width, height):
        if image is None:
            cv2.rectangle(canvas, (x, y), (x + width, y + height), (70, 70, 70), 2)
            cv2.putText(canvas, "NO IMAGE", (x + 28, y + height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (170, 170, 170), 2)
            return

        resized = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
        if resized.shape[2] == 4:
            rgb = resized[:, :, :3]
            alpha = resized[:, :, 3:4] / 255.0
            region = canvas[y : y + height, x : x + width]
            canvas[y : y + height, x : x + width] = (alpha * rgb + (1 - alpha) * region).astype(canvas.dtype)
        else:
            canvas[y : y + height, x : x + width] = resized

    def _draw_bin_gauge(self, canvas, x, y, width, height, fill, is_full):
        border = (60, 60, 60)
        fill_color = (45, 180, 80) if not is_full else (40, 40, 220)
        cv2.rectangle(canvas, (x, y), (x + width, y + height), border, 3)
        cv2.rectangle(canvas, (x + width // 5, y - 10), (x + width - width // 5, y), border, 3)

        if fill is None:
            cv2.putText(canvas, "N/A", (x + 20, y + height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (140, 140, 140), 2)
            return

        fill_height = int((height - 8) * max(0.0, min(1.0, fill)))
        top = y + height - 4 - fill_height
        cv2.rectangle(canvas, (x + 4, top), (x + width - 4, y + height - 4), fill_color, -1)
        cv2.putText(canvas, f"{int(round(fill * 100))}%", (x + 18, y + height + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, fill_color, 2)

    def _contains_hangul(self, text):
        return any("\uac00" <= char <= "\ud7a3" for char in str(text or ""))

    def _font_candidates(self, needs_korean):
        explicit_font = os.environ.get("SMART_BIN_KOREAN_FONT") or os.environ.get("SMART_BIN_FONT")
        if explicit_font:
            yield explicit_font

        korean_candidates = [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothicCoding.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf",
            "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
            "/usr/share/fonts/truetype/baekmuk/dotum.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        ]
        for font_path in korean_candidates:
            yield font_path

        for pattern in (
            "/usr/share/fonts/**/*Nanum*.ttf",
            "/usr/share/fonts/**/*Nanum*.otf",
            "/usr/share/fonts/**/*NotoSansCJK*.ttc",
            "/usr/share/fonts/**/*NotoSansCJK*.otf",
            "/usr/share/fonts/**/*NotoSerifCJK*.ttc",
            "/usr/share/fonts/**/*NotoSerifCJK*.otf",
            "/usr/share/fonts/**/*UnDotum*.ttf",
            "/usr/share/fonts/**/*Baekmuk*.ttf",
        ):
            yield from glob.iglob(pattern, recursive=True)

        if not needs_korean:
            yield "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    def _get_text_font(self, font_size, text=""):
        try:
            from PIL import ImageFont
        except Exception:
            return None

        needs_korean = self._contains_hangul(text)
        cache_key = (font_size, needs_korean)
        cached = self._font_cache.get(cache_key)
        if cached is not None:
            return cached

        seen = set()
        for font_path in self._font_candidates(needs_korean):
            if font_path in seen:
                continue
            seen.add(font_path)
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    self._font_cache[cache_key] = font
                    return font
                except Exception:
                    continue
        if needs_korean and not self._missing_korean_font_warned:
            print(
                "[Display] 한글 폰트를 찾지 못했습니다. Raspberry Pi에서 "
                "'sudo apt install fonts-nanum fonts-noto-cjk'를 실행하거나 "
                "SMART_BIN_KOREAN_FONT로 한글 TTF/TTC 경로를 지정하세요."
            )
            self._missing_korean_font_warned = True
        return None

    def _draw_text(self, canvas, text, x, y, font_size, color, thickness=2):
        font = self._get_text_font(font_size, text)
        if font is None:
            safe_text = text.encode("ascii", "replace").decode("ascii")
            cv2.putText(canvas, safe_text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_size / 36, color, thickness)
            return

        try:
            from PIL import Image, ImageDraw

            rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            draw = ImageDraw.Draw(pil_img)
            draw.text((x, y - font_size), text, font=font, fill=color[::-1])
            canvas[:] = cv2.cvtColor(np.asarray(pil_img), cv2.COLOR_RGB2BGR)
        except Exception:
            safe_text = text.encode("ascii", "replace").decode("ascii")
            cv2.putText(canvas, safe_text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_size / 36, color, thickness)

    def _classification_message(self):
        if self.selected_label:
            return f"{self.selected_label}으로 분류되었습니다"
        return self.message or "인식 대기"

    def render_frame(self):
        if cv2 is None or np is None:
            return None

        canvas = np.full((720, 1280, 3), (245, 245, 245), dtype=np.uint8)
        self._draw_text(canvas, self._classification_message(), 36, 72, 34, (35, 35, 35), 2)

        card_w = 280
        gap = 28
        start_x = 36
        card_y = 138
        for idx, label in enumerate(self.BIN_ORDER):
            x = start_x + idx * (card_w + gap)
            is_selected = label == self.selected_label
            is_full = label in self.full_bins
            outline = (20, 130, 255) if is_selected else (205, 205, 205)
            if is_full:
                outline = (40, 40, 220)
            cv2.rectangle(canvas, (x, card_y), (x + card_w, card_y + 530), outline, 3)

            self._paste_image(canvas, self._load_asset(label), x + 35, card_y + 25, 210, 210)
            cv2.putText(canvas, label, (x + 36, card_y + 280), cv2.FONT_HERSHEY_SIMPLEX, 0.92, (35, 35, 35), 2)
            if is_selected:
                cv2.putText(canvas, "SELECTED", (x + 36, card_y + 314), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (20, 130, 255), 2)
            if is_full:
                cv2.putText(canvas, "FULL", (x + 168, card_y + 314), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (40, 40, 220), 2)

            self._draw_bin_gauge(
                canvas,
                x + 78,
                card_y + 350,
                124,
                120,
                self.fill_levels.get(label),
                is_full,
            )

        return canvas

    def _show_frame(self):
        frame = self.render_frame()
        if frame is None or not self.enable_window:
            return

        try:
            if not self._window_ready:
                cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(self.window_name, 1280, 720)
                self._window_ready = True
            cv2.imshow(self.window_name, frame)
            cv2.waitKey(1)
        except Exception:
            self.enable_window = False

    def showClassificationStatus(self, label, confidence=None, fill_levels=None, full_bins=None, message=None):
        self.selected_label = self._normalize_bin_key(label) or str(label)
        self.confidence = confidence
        self.fill_levels = self._normalize_fill_levels(fill_levels)
        self.full_bins = {
            normalized
            for normalized in (self._normalize_bin_key(item) for item in (full_bins or []))
            if normalized
        }
        self.message = message or "분류 결과 표시"
        print(f"[Display] 분류 결과 '{self.selected_label}' / confidence={confidence} / fill={self.fill_levels}")
        self.refreshScreen()

    def showCategory(self, icon, text, confidence=None, fill_levels=None, full_bins=None):
        if confidence is not None or fill_levels is not None or full_bins is not None:
            return self.showClassificationStatus(text or icon, confidence, fill_levels, full_bins)

        self.selected_label = self._normalize_bin_key(text or icon) or text or icon
        self.message = "분류 결과 표시"
        print(f"[Display] 화면에 {icon} 아이콘 / 텍스트 '{text}' 표시")
        self.refreshScreen()

    def showWarning(self, message):
        self.message = message
        print(f"[Display] 경고: {message}")
        self.refreshScreen()

    def showBinFullWarning(self, message, fill_levels=None, full_bins=None):
        self.selected_label = None
        self.confidence = None
        self.fill_levels = self._normalize_fill_levels(fill_levels)
        self.full_bins = {
            normalized
            for normalized in (self._normalize_bin_key(item) for item in (full_bins or []))
            if normalized
        }
        self.message = message
        print(f"[Display] 경고: {message} / full={sorted(self.full_bins)}")
        self.refreshScreen()

    def showSensorSnapshot(self, fill_levels=None, full_bins=None, message="인식 대기"):
        self.fill_levels = self._normalize_fill_levels(fill_levels)
        self.full_bins = {
            normalized
            for normalized in (self._normalize_bin_key(item) for item in (full_bins or []))
            if normalized
        }
        self.message = message or "인식 대기"
        print(f"[Display] 센서 스냅샷 갱신 / fill={self.fill_levels}")
        self.refreshScreen()

    def refreshScreen(self):
        print("[Display] 화면 갱신")
        self._show_frame()

    def show_category(self, text):
        self.showCategory(text, text)

    def show_warning(self, msg):
        self.showWarning(msg)


class AudioC:
    def __init__(self):
        self.volume = 5
        self.category = {
            "페트병": "플라스틱",
            "플라스틱": "플라스틱",
            "종이": "일반",
            "스티로폼": "일반",
            "비닐": "일반",
            "금속캔": "캔",
            "건전지": "캔",
            "유리병": "유리",
            "형광등": "유리",
            
            "Plastic": "플라스틱",
            "plastic": "플라스틱",
            "Can": "캔",
            "can": "캔",
            "Glass": "유리",
            "glass": "유리",
            "Paper": "일반",
            "paper": "일반"
        }
        
        self.audio_files = {
            "플라스틱": "/home/trash/Downloads/plastic.mp3",
            "일반": "/home/trash/Downloads/general.mp3",
            "캔": "/home/trash/Downloads/can.mp3",
            "유리": "/home/trash/Downloads/glass.mp3",
        }
        self.effect_path = "/home/trash/Downloads/YCOIN.mp3"

    def playEffect(self, soundType: SoundType):
        print(f"[Audio] 효과음 재생: {soundType.value}")
        self._play_file(self.effect_path)

    def play_voice(self, category_name):
        path = self.audio_files.get(category_name)
        print(f"[Audio] 음성 안내 재생: {category_name} ({path})")
        self._play_file(path)

    def _play_file(self, path):
        if not pygame or not path or not os.path.exists(path):
            print(f"[Audio] ⚠️ 오디오 파일을 찾을 수 없거나 모듈 오류: {path}")
            return
            
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound = pygame.mixer.Sound(path)
            sound.play()
        except Exception as e:
            print(f"[Audio] MP3 재생 에러: {e}")

    def play_tts(self, text):
        text = (text or "").strip()
        mapped = self.category.get(text, "일반")
        
        self.playEffect(SoundType.SUCCESS)
        sleep(0.5)
        self.play_voice(mapped)


class MotorC:
    ANGLE_MAP = {
        "Paper": (90, 135),
        "Unknown": (90, 135),
        "Can": (90, 45),
        "Plastic": (15, 135),
        "Glass": (15, 45),
    }

    def __init__(self, pinNumber=None, bottom_pin=18, top_pin=19, move_delay=1.0):
        self.currentAngle = 0
        self.bottom_pin = pinNumber if pinNumber is not None else bottom_pin
        self.top_pin = top_pin
        self.pinNumber = self.bottom_pin
        self.move_delay = move_delay
        self.bottom_servo = None
        self.top_servo = None
        self.bottom_angle = 0
        self.top_angle = 90
        self.command_log = []

        if AngularServo is not None and _GPIO_FACTORY is not None:
            try:
                self.bottom_servo = AngularServo(
                    self.bottom_pin,
                    min_angle=0,
                    max_angle=180,
                    min_pulse_width=0.0005,
                    max_pulse_width=0.0025,
                    initial_angle=None,
                    pin_factory=_GPIO_FACTORY,
                )
                self.top_servo = AngularServo(
                    self.top_pin,
                    min_angle=0,
                    max_angle=180,
                    min_pulse_width=0.0005,
                    max_pulse_width=0.0025,
                    initial_angle=None,
                    pin_factory=_GPIO_FACTORY,
                )
            except Exception:
                self.bottom_servo = None
                self.top_servo = None

        self.reset_motors()

    def _sleep_after_move(self):
        if self.move_delay and (self.bottom_servo is not None or self.top_servo is not None):
            sleep(self.move_delay)

    def _detach_servo(self, servo):
        if servo is None:
            return
        detach = getattr(servo, "detach", None)
        if callable(detach):
            try:
                detach()
                return
            except Exception:
                pass
        try:
            servo.value = None
        except Exception:
            pass

    def _detach_motors(self):
        self._detach_servo(self.bottom_servo)
        self._detach_servo(self.top_servo)

    def _set_bottom_angle(self, angle):
        self.bottom_angle = angle
        self.currentAngle = angle
        self.command_log.append(("bottom", angle))
        if self.bottom_servo is not None:
            self.bottom_servo.angle = angle

    def _set_top_angle(self, angle):
        self.top_angle = angle
        self.command_log.append(("top", angle))
        if self.top_servo is not None:
            self.top_servo.angle = angle

    def _category_value(self, received_value):
        value = getattr(received_value, "value", received_value)
        if value in self.ANGLE_MAP:
            return value
        return "Unknown"

    def reset_motors(self):
        self._set_bottom_angle(0)
        self._set_top_angle(90)
        self._sleep_after_move()
        self._detach_motors()

    def process_item(self, received_value):
        category = self._category_value(received_value)
        bottom_angle, top_angle = self.ANGLE_MAP.get(category, self.ANGLE_MAP["Unknown"])

        print(f"\n[Motor] '{category}' 분류를 시작합니다.")
        print(f"[Motor] 하단 모터 {bottom_angle}도로 이동")
        self._set_bottom_angle(bottom_angle)
        self._sleep_after_move()

        print(f"[Motor] 상단 모터 {top_angle}도로 이동")
        self._set_top_angle(top_angle)
        self._sleep_after_move()

        print("[Motor] 모터 초기화: 하단 0도, 상단 90도")
        self.reset_motors()
        print("[Motor] 분류 완료")

    def resetPosition(self):
        self.reset_motors()

    def rotateTo(self, angle):
        self._set_bottom_angle(angle)
        print(f"[Motor] {angle}도로 회전하여 분류")

    def sendPWM(self, pulseWidth):
        print(f"[Motor] PWM 전송: pin={self.pinNumber}, pulse={pulseWidth}")

    def rotate_to(self, angle):
        self.rotateTo(angle)


class SensorC:
    def __init__(self, fillThreshold=0.8, trig=23, echo=25, height_dist=720):
        self.fillThreshold = fillThreshold
        self.empty_bin_dist = height_dist / 10.0
        self.sensor = None

        if DistanceSensor is not None and _GPIO_FACTORY is not None:
            try:
                self.sensor = DistanceSensor(
                    echo=echo,
                    trigger=trig,
                    pin_factory=_GPIO_FACTORY,
                )
            except Exception:
                self.sensor = None

    def checkFillLevel(self):
        if self.sensor is not None:
            current_dist = self.sensor.distance * 100
            filled_height = self.empty_bin_dist - current_dist
            fill_ratio = filled_height / self.empty_bin_dist
            return max(0.0, min(1.0, fill_ratio))

        analog = self.readAnalogValue()
        return max(0.0, min(1.0, analog / 1023.0))

    def isFull(self):
        return self.checkFillLevel() >= self.fillThreshold

    def readAnalogValue(self):
        if self.sensor is not None:
            current_dist = self.sensor.distance * 100
            if current_dist > self.empty_bin_dist:
                current_dist = self.empty_bin_dist
            return (current_dist / self.empty_bin_dist) * 100
        return 0

    def is_full(self):
        return self.isFull()


class BluetoothC:
    def __init__(self, server=None, notifier: BleNotifier | None = None):
        self.isConnected = False
        self.server = server
        self.notifier = notifier or MockBleNotifier()

        if self.server is None and notifier is None:
            self.server = EmbeddedBleServer()

    def connect(self):
        if self.server is not None:
            self.isConnected = self.server.start()
            if self.isConnected:
                print("[Bluetooth] BLE 서버 연결 준비 완료")
            else:
                print("[Bluetooth] BLE 서버 시작 실패")
            return self.isConnected

        self.isConnected = True
        return self.isConnected

    def sendEvent(self, event, message):
        if not self.isConnected:
            if not self.connect():
                return False

        if self.server is not None:
            ok = self.server.send_event(event, message)
            if ok:
                print(f"[Bluetooth] 스마트폰 앱으로 알림 전송: [{event}] {message}")
            else:
                print(f"[Bluetooth] 스마트폰 앱 알림 전송 실패: [{event}] {message}")
            return ok

        return self.notifier.notify(event, message)

    def sendAlert(self, message):
        return self.sendEvent("BIN_FULL", message)

    def sendExceptionAlert(self, message):
        return self.sendEvent("OUTPUT_EXCEPTION", message)

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