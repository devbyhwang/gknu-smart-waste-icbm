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

class MotorC: # 혹은 SortingSystem
    def __init__(self, bottom_pin=17, top_pin=27):
        # 1. 하단 모터 세팅
        self.bottom_servo = AngularServo(
            bottom_pin, min_angle=0, max_angle=180, 
            min_pulse_width=0.0005, max_pulse_width=0.0025, pin_factory=factory
        )
        # 2. 상단 모터 세팅
        self.top_servo = AngularServo(
            top_pin, min_angle=0, max_angle=180, 
            min_pulse_width=0.0005, max_pulse_width=0.0025, pin_factory=factory
        )
        
        # 3. 각도 지도 세팅
        self.angle_map = {
            WasteCategory.CAN: 45,
            WasteCategory.PLASTIC: 90,
            WasteCategory.GLASS: 135,
            WasteCategory.PAPER: 180,
            WasteCategory.UNKNOWN: 180
        }

    def process_item(self, received_value):
        # [단계 1] 카테고리 판별
        try:
            category = WasteCategory(received_value)
        except ValueError:
            category = WasteCategory.UNKNOWN

        target_angle = self.angle_map.get(category)

        # [단계 2] 하단 모터 구동
        self.bottom_servo.angle = target_angle
        sleep(1.0)

        # [단계 3] 상단 모터 구동 (드롭)
        self.top_servo.angle = 70
        sleep(1.0)

        # [단계 4] 상단 모터 복귀
        self.top_servo.angle = 0
        sleep(1.0)
        