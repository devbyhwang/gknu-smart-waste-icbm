# EcoSort-AIoT

YOLOv8 + Raspberry Pi 기반 온디바이스(On-device) 폐기물 자동 분류 시스템  

## Project Overview

- Raspberry Pi 4에서 YOLO로 폐기물을 온디바이스 분류합니다.
- 분류 결과를 Servo Motors 제어로 연결해 자동 분류 동작을 수행합니다.

## Key Features

- Real-time AI Vision: YOLOv8 기반 고속 객체 탐지.
- Precision Actuator Control: 분류 결과 기반 Servo 정밀 제어.

## System Architecture

- IoT: Raspberry Pi 4, Servo Motors, IR/Ultrasonic Sensors
- AI: YOLOv8 Nano (Optimized for Edge)
- Mobile: Local Network/Bluetooth 알림 채널

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
├── mobile/
└── sensors/
```
