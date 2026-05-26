import cv2
import os
from enum import Enum
import time

# 카테고리 정의 (기존과 동일)
class WasteCategory(Enum):
    CAN = "Can"
    PLASTIC = "Plastic"
    GLASS = "Glass"
    PAPER = "Paper"
    UNKNOWN = "Unknown"

class DisplayC:
    def __init__(self):
        """디스플레이 창 초기 설정"""
        self.window_name = "Smart Bin Display"
        
        # 창을 만들고, 라즈베리파이 화면에 꽉 차게(전체화면) 설정합니다.
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        # 초기 대기 화면 (검은 화면 또는 대기 이미지)
        self._show_standby()

    def _show_standby(self):
        """기본 대기 화면 (검은색 배경)"""
        # 아무것도 없을 때는 까만 화면을 띄워둡니다.
        import numpy as np
        black_screen = np.zeros((600, 800, 3), dtype=np.uint8)
        cv2.imshow(self.window_name, black_screen)
        cv2.waitKey(1)

    def show_category_image(self, received_value):
        """결과 값을 받아 해당하는 이미지를 화면에 띄우는 함수"""
        
        # 1. 텍스트 값을 안전하게 카테고리로 변환
        try:
            category = WasteCategory(received_value)
        except ValueError:
            category = WasteCategory.UNKNOWN

        # 2. 불러올 이미지 파일 이름 규칙 정하기 (예: Can -> assets/can.png)
        img_name = category.value.lower() # "Can" -> "can"
        img_path = f"assets/{img_name}.png"
        
        # 3. 이미지 띄우기
        if os.path.exists(img_path):
            img = cv2.imread(img_path)
            cv2.imshow(self.window_name, img)
            
            # ⭐️ OpenCV에서 창을 새로고침하고 유지하기 위한 필수 코드 (1밀리초 대기)
            cv2.waitKey(1) 
            print(f"🖥️ 디스플레이 출력 완료: {img_path}")
        else:
            print(f"⚠️ 이미지를 찾을 수 없습니다: {img_path}")
            self._show_standby()
