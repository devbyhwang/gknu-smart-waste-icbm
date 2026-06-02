from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class WasteType(Enum):
    # 시스템 전체에서 쓰는 표준 쓰레기 종류.
    CAN = "Can"
    PLASTIC = "Plastic"
    GLASS = "Glass"
    PAPER = "Paper"
    UNKNOWN = "Unknown"


@dataclass
class ClassificationResult:
    # 추론 결과를 출력 계층으로 넘길 때 사용하는 값 객체.
    label: WasteType
    confidence: float


class HandleClassificationResult(ABC):
    # 추론 계층은 이 인터페이스만 알고, 실제 화면/모터 구현에는 직접 의존하지 않는다.
    @abstractmethod
    def handleClassification(self, result: ClassificationResult):
        raise NotImplementedError

    def handle_classification(self, result: ClassificationResult):
        # Backward-compatible alias for snake_case callers.
        return self.handleClassification(result)
