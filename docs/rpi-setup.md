# Raspberry Pi 설치 및 용량 문제 해결 가이드

이 문서는 `EcoSort-AIoT`를 라즈베리파이에서 설치할 때 발생하는 용량 부족(`No space left on device`) 문제를 포함해, 설치부터 진단/복구까지 한 번에 정리한 가이드입니다.

## 1) 대상 환경 및 전제

- OS: Raspberry Pi OS (권장: Bookworm 계열)
- 저장소: 32GB SD 카드 기준
- 예시 프로젝트 경로: `~/nashville`
- Python 가상환경(`venv`) 사용 기준
- Python UI 안내창을 표시하려면 Raspberry Pi OS Desktop 또는 X11/Wayland 디스플레이 세션이 필요합니다.

32GB SD 카드라도 실제 사용 가능 용량은 시스템 파티션/로그/캐시 때문에 더 작게 보일 수 있습니다. 설치 전 여유공간을 먼저 확인하세요.

## 2) 기본 설치 순서 (저장공간 절약형)

`pytest`는 런타임에 불필요하므로 제외하고 설치합니다.

```bash
cd ~/nashville

# 가상환경 생성/활성화
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip

# 런타임 전용 requirements 생성 (pytest 제외)
grep -v '^pytest' requirements.txt > requirements.rpi.txt

# 캐시 없이 설치 + piwheels 사용
python -m pip install --no-cache-dir \
  -r requirements.rpi.txt \
  --extra-index-url https://www.piwheels.org/simple
```

실행:

```bash
python -m src.main
```

카메라 오버레이와 출력 핸들러를 함께 확인:

```bash
python -m src.main --test-mode --test-dispatch
```

## 3) Python UI 안내창 실행 전 확인

Python UI 안내창은 현장 사용자에게 분류 결과와 쓰레기 적재량을 보여주는 로컬 화면입니다.

- 한글 상단 문구가 네모/깨진 글자로 보이면 한글 폰트가 없는 상태입니다.
  - DisplayC는 OpenCV 기본 폰트가 아니라 Pillow + 시스템 한글 폰트로 한글을 렌더링합니다.
  - Raspberry Pi OS 기본 폰트인 DejaVu에는 한글 글리프가 없어 사용할 수 없습니다.
  - 아래 패키지를 설치하세요.

```bash
sudo apt update
sudo apt install -y fonts-nanum fonts-noto-cjk
fc-cache -f
```

- 별도 한글 폰트 파일을 쓰려면 실행 전에 경로를 지정할 수 있습니다.

```bash
export SMART_BIN_KOREAN_FONT=/path/to/KoreanFont.ttf
python -m src.main
```

- Desktop 환경에서 실행하는 경우:
  - HDMI/터치 디스플레이 연결 확인
  - Raspberry Pi OS Desktop 로그인 후 터미널에서 실행
  - `echo $DISPLAY` 결과가 비어 있지 않은지 확인
- SSH에서 실행하는 경우:
  - X11 forwarding 또는 원격 데스크톱 환경이 없으면 UI 창이 뜨지 않을 수 있음
  - 장비 실기 검증은 가능하면 Pi에 연결된 실제 화면에서 진행
- 표시해야 하는 정보:
  - 분류 라벨과 confidence
  - `SensorC.checkFillLevel()` 기준 적재량 퍼센트
  - `SensorC.isFull()` true일 때 "분류함이 가득 찼습니다!" 경고
  - 센서 오류 시 "적재량 확인 불가"

## 4) 용량 부족 진단 명령

어디가 찼는지 먼저 확인합니다.

```bash
# 파일시스템/파티션 상태
df -h
lsblk

# 루트(/)와 /var의 대용량 디렉터리 탐색
sudo du -xhd1 / | sort -h
sudo du -xhd1 /var | sort -h

# 사용자 영역 캐시/프로젝트 용량
du -sh ~/.cache ~/.local ~/nashville 2>/dev/null
```

## 5) 즉시 정리 명령

아래 명령은 일반적으로 안전한 정리 절차입니다.

```bash
sudo apt clean
sudo apt autoremove --purge -y
sudo journalctl --vacuum-size=50M

rm -rf ~/.cache/pip
rm -rf ~/.cache/ultralytics
```

필요 시(개인 환경 기준) 추가 점검:

```bash
sudo du -xhd1 /var/log | sort -h
```

## 6) 루트 파티션 확장 (가장 흔한 원인)

SD 카드가 32GB여도 루트 파티션이 확장되지 않으면 실제로는 몇 GB만 쓸 수 있습니다.

```bash
sudo raspi-config
```

- `Advanced Options` -> `Expand Filesystem`
- 재부팅 후 확인:

```bash
df -h
```

`/` 용량이 SD 카드 크기(대략 29GB 전후)로 보이는지 확인하세요.

## 7) 그래도 실패할 때 대안

### A. OpenCV를 apt 패키지로 전환

pip `opencv-python` 대신 시스템 패키지를 사용하면 빌드/설치 부담을 줄일 수 있습니다.

```bash
sudo apt update
sudo apt install -y python3-opencv

cd ~/nashville
python3 -m venv .venv --system-site-packages
source .venv/bin/activate

# opencv-python/pytest 제외 후 설치
grep -Ev '^(opencv-python|pytest)' requirements.txt > requirements.rpi.txt
python -m pip install --no-cache-dir \
  -r requirements.rpi.txt \
  --extra-index-url https://www.piwheels.org/simple
```

### B. Raspberry Pi OS Lite 사용

Desktop 버전보다 Lite가 저장공간 사용량이 작아 설치 안정성이 높습니다.

단, Lite 환경은 기본 GUI 세션이 없으므로 Python UI 안내창을 바로 띄우기 어렵습니다. Lite를 사용할 경우 별도 디스플레이 서버, 원격 데스크톱, 또는 콘솔 대체 표시 방식을 준비해야 합니다.

### C. 외장 스토리지 사용

프로젝트/가상환경/모델 파일을 USB SSD로 이동해 SD 카드 압박을 줄입니다.

## 8) 최소 여유공간 가이드 및 체크리스트

- 권장 여유공간: 최소 6~8GB
- 설치 직전 점검:
  - `df -h`에서 `/` 사용률이 80% 미만인지 확인
  - `raspi-config`로 루트 파티션 확장 여부 확인
  - `~/.cache/pip`, `~/.cache/ultralytics` 정리 여부 확인
  - `requirements.rpi.txt`로 런타임 의존성만 설치하는지 확인
  - Python UI 검증이 필요하면 Desktop 세션과 `$DISPLAY` 확인

자주 발생하는 원인:

- 루트 파티션 미확장
- pip 캐시 누적
- Desktop OS 기본 패키지로 인한 여유공간 부족
- `opencv-python`/`torch` 설치 중 임시 파일 누적
