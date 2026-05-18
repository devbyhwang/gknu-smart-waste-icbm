# EcoSort-AIoT

YOLOv8 + Raspberry Pi 기반 온디바이스(On-device) 폐기물 자동 분류 시스템  

## Project Overview

- Raspberry Pi 4에서 YOLO로 폐기물을 온디바이스 분류합니다.
- 분류 결과를 Servo Motors 제어로 연결해 자동 분류 동작을 수행합니다.
- 로컬 Python UI 화면창으로 현재 분류 결과와 분류함 적재 상태를 사용자에게 안내합니다.

## Key Features

- Real-time AI Vision: YOLOv8 기반 고속 객체 탐지.
- Precision Actuator Control: 분류 결과 기반 Servo 정밀 제어.
- Local Display UI: Python 안내창에 분류 라벨, confidence, 쓰레기 적재량/가득 참 경고 표시.
- BLE Notification: 분류함 가득 참 등 주요 이벤트를 Android 앱으로 notify 전송.

## System Architecture

- IoT: Raspberry Pi 4, Servo Motors, IR/Ultrasonic Sensors
- AI: YOLOv8 Nano (Optimized for Edge)
- Display: Python UI window for local user guidance
- Mobile: Local Network/Bluetooth 알림 채널

## Runtime Flow

```text
Camera/Sensor
  -> YOLO 분류
  -> OutputM
  -> Servo 분류 동작
  -> Python UI 안내창 갱신
  -> BLE Notify / Android 앱 알림
```

## Python Display UI

MVP에서는 별도 웹/모바일 화면이 없어도 Raspberry Pi에 연결된 디스플레이에서 사용자가 즉시 상태를 볼 수 있어야 합니다.

- 표시 정보:
  - 현재 분류 결과: `Can`, `Plastic`, `Glass`, `Paper`, `Unknown`
  - 모델 confidence
  - 쓰레기 적재량: `SensorC.checkFillLevel()` 기준 0~100%
  - 상태 메시지: 정상 분류, 인식 대기, 분류함 가득 참, 장치 예외
- 동작 기준:
  - `OutputM.handleClassification()` 처리 시 화면을 즉시 갱신합니다.
  - 적재량이 `SensorC.fillThreshold` 이상이면 "분류함이 가득 찼습니다!" 경고를 표시합니다.
  - 센서 값을 읽을 수 없으면 UI는 중단하지 않고 "적재량 확인 불가" 상태를 표시해야 합니다.
  - 테스트 모드에서는 카메라 오버레이와 별도로 Python 안내창 동작을 확인할 수 있어야 합니다.

## Class Diagram

![EcoSort Class Diagram](docs/images/class-diagram.png)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## Install Dependencies

```bash
python -m pip install -r requirements.txt
```

Raspberry Pi 설치 및 용량 문제 해결 가이드: [docs/rpi-setup.md](docs/rpi-setup.md)

## Run

```bash
python -m src.main
```

테스트 모드(카메라 화면 + YOLO 인식 오버레이):

```bash
python -m src.main --test-mode
```

테스트 모드에서 현재 핸들러 동작까지 함께 확인:

```bash
python -m src.main --test-mode --test-dispatch
```

Python UI 안내창 구현 후에는 일반 실행과 테스트 디스패치 실행 모두에서 분류 결과/적재량 화면 갱신을 확인합니다.

## BLE Notify

`python -m src.main` 실행 시 출력 핸들러가 필요할 때 Raspberry Pi BLE Notify 서버를 시작합니다. Android 앱은 아래 GATT characteristic을 notify 구독해야 합니다.

```text
Name: RaspberryPi_BLE
Service UUID: f82d9a22-3dc9-430e-875d-583c9ced1904
Characteristic UUID: 2c5bba85-ac1c-46c2-a8d3-db389101a028
Payload: {"event": "...", "message": "...", "ts": "..."}
```

## Test

```bash
python -m pytest tests/
```

## Project Structure

### Current

```text
.
├── src/
└── tests/
```

### Planned

```text
src/
├── display_ui.py
├── mobile/
└── sensors/
```
