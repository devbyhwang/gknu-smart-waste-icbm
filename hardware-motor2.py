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
        # 1. 하단 모터 세팅 (18번 핀)
        self.bottom_servo = AngularServo(
            bottom_pin, min_angle=0, max_angle=180, 
            min_pulse_width=0.0005, max_pulse_width=0.0025, pin_factory=factory
        )
        
        # 2. 상단 모터 세팅 (19번 핀)
        self.top_servo = AngularServo(
            top_pin, min_angle=0, max_angle=180, 
            min_pulse_width=0.0005, max_pulse_width=0.0025, pin_factory=factory
        )
        
        # 3. 각도 지도 세팅 (하단 모터 각도, 상단 모터 각도)
        self.angle_map = {
            WasteCategory.PAPER:   (90, 135),
            WasteCategory.UNKNOWN: (90, 135),
            WasteCategory.CAN:     (90, 45),
            WasteCategory.PLASTIC: (15, 135),
            WasteCategory.GLASS:   (15, 45)
        }
        
        # 시스템 켤 때 초기 위치로 세팅 (하단 0도, 상단 90도)
        self.reset_motors()

    def reset_motors(self):
        """★ 수정: 하단 모터는 0도, 상단 모터는 90도로 되돌리는 함수"""
        self.bottom_servo.angle = 0
        self.top_servo.angle = 90
        sleep(1.0) # 모터가 제자리로 돌아갈 시간을 줌

    def process_item(self, received_value):
        # [단계 1] 카테고리 판별
        try:
            category = WasteCategory(received_value)
        except ValueError:
            category = WasteCategory.UNKNOWN

        # 목표 각도 꺼내오기
        bottom_angle, top_angle = self.angle_map.get(category, (90, 135))
        
        print(f"\n[모터 구동] '{category.value}' 분류를 시작합니다.")

        # [단계 2] 하단 모터 구동 (길 열어주기)
        print(f" 1. 하단 모터 {bottom_angle}도로 이동")
        self.bottom_servo.angle = bottom_angle
        sleep(1.0)

        # [단계 3] 상단 모터 구동 (쓰레기 투하)
        print(f" 2. 상단 모터 {top_angle}도로 이동 (투하)")
        self.top_servo.angle = top_angle
        sleep(1.0)

        # [단계 4] 초기 위치로 복귀 (하단 0도, 상단 90도)
        print(" 3. 모터 초기화 (하단 0도, 상단 90도)")
        self.reset_motors()
        print("[분류 완료]")