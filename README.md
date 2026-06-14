# EcoSort-AIoT Smart Waste Classifier

GKNU 국립경국대학교 컴퓨터공학과 ICBM 기반 캡스톤디자인 4명 팀 프로젝트입니다.

카메라 영상과 YOLO 객체 탐지를 이용해 쓰레기 종류를 인식하고, 초음파 센서로 분류함의 적재 상태를 확인한 뒤 화면, 음성, 서보모터, BLE 알림으로 분류 결과를 출력하는 스마트 분리수거 시스템입니다.

## 연관 저장소

- 안드로이드 알람 BLE 애플리케이션: [ANU_EcoSortBleClient](https://github.com/devbyhwang/ANU_EcoSortBleClient.git)

## 주요 기능

- Raspberry Pi 카메라 스트림 수집
- YOLO 기반 쓰레기 객체 탐지
- 연속 인식 횟수와 confidence 기준을 이용한 분류 검증
- 초음파 센서 기반 분류함 채움 상태 확인
- 분류함 가득참 시 모터 동작 차단
- OpenCV 화면 표시
- 음성 안내 및 경고음 출력
- Android 앱 연동을 위한 BLE 알림 전송

## 시스템 흐름

1. `CameraManager`가 `rpicam-vid`로 카메라 프레임을 읽습니다.
2. `InferenceEngine`이 YOLO 모델로 쓰레기 라벨, confidence, bbox를 예측합니다.
3. `WasteClassifier`가 confidence와 연속 인식 횟수를 기준으로 결과를 검증합니다.
4. 검증이 통과되면 `OutputM`이 센서 상태를 확인합니다.
5. 분류함이 가득 차지 않았으면 화면, 음성, 모터 동작을 수행합니다.
6. 분류함이 가득 찼으면 모터를 움직이지 않고 화면 경고, 경고음, BLE 알림을 보냅니다.

## 프로젝트 구조

```text
.
├── Docs/UML/diagrams.md       # UML 문서
├── img/                       # 화면 표시용 분류함 이미지
├── mp3/                       # 음성 파일 리소스
├── requirements.txt           # Python dependencies
└── src/
    ├── main.py                # 실행 진입점
    ├── camera.py              # Raspberry Pi 카메라 프레임 수집
    ├── inference.py           # YOLO 추론 및 분류 검증 루프
    ├── output_mgr.py          # 화면/음성/모터/센서/BLE 출력 통합
    ├── hardware.py            # 하드웨어 어댑터
    ├── ble_notify.py          # BLE GATT notify server
    ├── models.py              # 공통 enum/dataclass/interface
    └── mobile/
        └── ble_notifier.py    # BLE 알림 mock/test adapter
```

## 하드웨어 구성

- Raspberry Pi
- Raspberry Pi Camera
- 초음파 센서 4개
- 서보모터 2개
- 스피커 또는 오디오 출력 장치
- BLE를 수신하는 Android 앱

기본 센서 GPIO 핀 설정은 `src/output_mgr.py`의 `BIN_SENSOR_CONFIG`에 정의되어 있습니다.

```python
WasteType.CAN: {"trig": 23, "echo": 25}
WasteType.PLASTIC: {"trig": 17, "echo": 27}
WasteType.GLASS: {"trig": 22, "echo": 24}
WasteType.PAPER: {"trig": 5, "echo": 6}
```

기본 모터 핀은 `src/hardware.py`의 `MotorC`에 정의되어 있습니다.

```python
bottom_pin = 18
top_pin = 19
```

## 설치

Python 가상환경을 만든 뒤 의존성을 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Raspberry Pi에서 GPIO 서보 제어를 사용하려면 `gpiozero`와 `lgpio` 계열 패키지가 필요합니다. 코드에서는 해당 패키지가 없을 때도 개발 환경에서 import가 실패하지 않도록 처리합니다.

## 모델 파일

기본 모델 경로는 `best.pt`입니다.

```bash
python3 src/main.py --model-path best.pt
```

`--model-path`가 상대 경로이면 실행 위치, 프로젝트 루트, `src` 디렉터리 기준으로 모델 파일을 찾습니다.

## 실행

```bash
python3 src/main.py
```

주요 실행 옵션:

```bash
python3 src/main.py \
  --model-path best.pt \
  --camera-index 0 \
  --width 640 \
  --height 480 \
  --fps 15 \
  --max-count 3 \
  --interval-ms 200 \
  --conf-thres 0.1 \
  --imgsz 320 \
  --device cpu
```

옵션 설명:

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--model-path` | `best.pt` | YOLO 모델 파일 경로 |
| `--camera-index` | `0` | Raspberry Pi 카메라 번호 |
| `--width` | `640` | 카메라 프레임 너비 |
| `--height` | `480` | 카메라 프레임 높이 |
| `--fps` | `15` | 카메라 FPS |
| `--max-count` | `3` | 같은 라벨이 연속 감지되어야 하는 횟수 |
| `--interval-ms` | `200` | YOLO 추론 간격 |
| `--conf-thres` | `0.1` | YOLO confidence threshold |
| `--imgsz` | `320` | YOLO 입력 이미지 크기 |
| `--device` | `cpu` | YOLO 실행 장치 |

실행 중 종료는 카메라 창에서 `q` 또는 `ESC`를 누릅니다.

## 분류 라벨

시스템 표준 분류는 다음 5가지입니다.

- `Can`
- `Plastic`
- `Glass`
- `Paper`
- `Unknown`

모델이 한글 라벨을 반환하더라도 `src/inference.py`의 `LABEL_ALIASES`를 통해 표준 라벨로 변환합니다.

## 가득참 처리

`OutputM.handleClassification()`은 분류 동작 전에 각 분류함의 채움 상태를 확인합니다.

- 분류함이 정상 상태이면 화면 표시, 음성 안내, 모터 분류를 수행합니다.
- 하나 이상의 분류함이 가득 찼으면 모터를 움직이지 않습니다.
- 화면에 경고를 표시하고, 경고음을 재생하고, Android 앱으로 `BIN_FULL` BLE 이벤트를 전송합니다.

## BLE 알림

BLE 서버는 `src/ble_notify.py`의 `EmbeddedBleServer`가 담당합니다.

기본 BLE 정보:

```text
Device Name: RaspberryPi_BLE
Service UUID: f82d9a22-3dc9-430e-875d-583c9ced1904
Characteristic UUID: 2c5bba85-ac1c-46c2-a8d3-db389101a028
```

BLE payload는 JSON 형식입니다.

```json
{
  "event": "BIN_FULL",
  "message": "Can 분류함 비움 필요",
  "ts": "2026-06-06T00:00:00+00:00"
}
```

## 참고 문서

코드 구조와 주요 실행 흐름은 다음 문서에 정리되어 있습니다.

- [Docs/UML/diagrams.md](Docs/UML/diagrams.md)
- [Class Diagram](Docs/UML/images/class-diagram.png)
- [Code Flow Sequence Diagram](Docs/UML/images/code-flow-sequence.png)
- [Full Bin Exception Sequence Diagram](Docs/UML/images/full-bin-exception-sequence.png)
- [User Sequence Diagram](Docs/UML/images/user-sequence.png)

## 개발 메모

- `src/main.py`가 실행 진입점입니다.
- `src/inference.py`는 카메라 루프, YOLO 추론, 연속 인식 검증을 담당합니다.
- `src/output_mgr.py`는 센서 확인과 출력 장치 제어를 조율합니다.
- `src/hardware.py`는 실제 하드웨어와 개발 환경 fallback을 함께 처리합니다.
- 개발 환경에서 카메라, GPIO, 오디오, BLE 장치가 없으면 일부 기능은 로그만 출력하거나 실패를 무시하고 계속 진행합니다.

## 팀

- GKNU 국립경국대학교 컴퓨터공학과
- ICBM 기반 캡스톤디자인
- 구성: Contributor 4인 팀 프로젝트
