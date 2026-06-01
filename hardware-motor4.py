from enum import Enum
from time import sleep
from gpiozero import AngularServo
from gpiozero.pins.lgpio import LGPIOFactory

factory = LGPIOFactory()

class WasteCategory(Enum):
    CAN = "Can"
    PLASTIC = "Plastic"
    GLASS = "Glass"
    PAPER = "Paper"
    UNKNOWN = "Unknown"

class MotorC:
    def __init__(self, bottom_pin=18, top_pin=19):
        # 모터 핀 번호만 기억해 둡니다. (여기서 조종기를 미리 만들지 않습니다!)
        self.bottom_pin = bottom_pin
        self.top_pin = top_pin
        
        self.angle_map = {
            WasteCategory.PAPER:   (90, 135),
            WasteCategory.UNKNOWN: (90, 135),
            WasteCategory.CAN:     (90, 45),
            WasteCategory.PLASTIC: (15, 135),
            WasteCategory.GLASS:   (15, 45)
        }
        
        # 시스템 켤 때 초기 위치로 한 번 세팅
        self.reset_motors()

    def reset_motors(self):
        """초기 위치(하단 0도, 상단 90도)로 맞추고 핀 연결을 닫습니다."""
        bottom_servo = AngularServo(
            self.bottom_pin, min_angle=0, max_angle=180, 
            min_pulse_width=0.0005, max_pulse_width=0.0025, pin_factory=factory
        )
        top_servo = AngularServo(
            self.top_pin, min_angle=0, max_angle=180, 
            min_pulse_width=0.0005, max_pulse_width=0.0025, pin_factory=factory
        )
        
        bottom_servo.angle = 0
        top_servo.angle = 90
        sleep(1.0) # 도착할 때까지 1초 기다림
        
        # ⭐️ 핵심: 조종기 연결을 완전히 파괴합니다. (지터링 방지 & 먹통 방지)
        bottom_servo.close()
        top_servo.close()

    def process_item(self, received_value):
        try:
            category = WasteCategory(received_value)
        except ValueError:
            category = WasteCategory.UNKNOWN

        bottom_angle, top_angle = self.angle_map.get(category, (90, 135))
        
        print(f"\n[모터 구동] '{category.value}' 분류를 시작합니다.")

        # ⭐️ 1. 분류 시작할 때 다시 조종기 생성 (initial_angle로 모터 튐 방지)
        bottom_servo = AngularServo(
            self.bottom_pin, min_angle=0, max_angle=180, 
            min_pulse_width=0.0005, max_pulse_width=0.0025, 
            initial_angle=0, pin_factory=factory
        )
        top_servo = AngularServo(
            self.top_pin, min_angle=0, max_angle=180, 
            min_pulse_width=0.0005, max_pulse_width=0.0025, 
            initial_angle=90, pin_factory=factory
        )

        # [단계 2] 하단 모터 구동
        print(f" 1. 하단 모터 {bottom_angle}도로 이동")
        bottom_servo.angle = bottom_angle
        sleep(1.0)

        # [단계 3] 상단 모터 구동
        print(f" 2. 상단 모터 {top_angle}도로 이동 (투하)")
        top_servo.angle = top_angle
        sleep(1.0)

        # [단계 4] 초기 위치로 복귀
        print(" 3. 모터 초기화 (하단 0도, 상단 90도)")
        bottom_servo.angle = 0
        top_servo.angle = 90
        sleep(1.0)
        
        # ⭐️ 2. 분류가 끝나면 핀 연결 완전 해제
        bottom_servo.close()
        top_servo.close()
        print("[분류 완료]")