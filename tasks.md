# Sprint Tasks - MVP Essential Only (2026-04-27 ~ 2026-05-15, updated 2026-05-18)

## 목표
- 이번 MVP는 아래 1개 흐름을 완성한다.
- `센서 감지 -> 분류 판단 -> 모터 동작 -> Python UI 안내창 갱신 -> BLE 전송 -> 안드로이드 앱 알림 수신`

## 공통 완료 기준
- 실기에서 위 흐름 1회 이상 성공 로그/영상 확보
- `python -m pytest tests/` 통과
- 각 담당 PR에 변경 요약 + 검증 로그 첨부
- Python UI 안내창에 분류 결과와 쓰레기 적재량/가득 참 경고가 표시되는 영상 또는 스크린샷 첨부

## 필수 작업 (7개)

| ID | 담당 | 작업 | 왜 필요한가 | 결과물 | 검증 방법 | 기한 | 선행 |
|---|---|---|---|---|---|---|---|
| E-01 | A | `inference.py` 다중 박스에서 최고 confidence 1개 선택으로 변경 | 현재 첫 박스 고정이라 오탐 가능성 큼 | 추론 선택 로직 | 다중 박스 입력 테스트에서 최고 conf 라벨 반환 | 4/29 | 없음 |
| E-02 | A | 카메라/모델 초기화 실패 처리 + 프레임 일시 실패 재시도 + 안전 종료(`release`) 보장 | 장치 오류/일시적 읽기 실패에서 서비스 안정성 확보 | 예외/종료/재시도 처리 로직 | 초기화 실패 안전 종료 + 프레임 일시 실패 복구 + 연속 실패 시 종료 확인 | 5/1 | 없음 |
| E-03 | B | `SensorC.readAnalogValue()` 실측값 반환으로 구현 (더미 0 제거) | 실제 센서 기반 트리거를 만들기 위해 필수 | 센서 읽기 구현 | 센서 상태 변화 시 반환값 변화 확인 | 5/2 | 없음 |
| E-04 | B | 서보 PWM 실제 호출 구현(print 제거) + 라벨별 각도 매핑 적용 | 분류 타입별 물리 분류가 달라져야 함 | 모터 제어/각도 매핑 구현 | 실기 0/90도 + 라벨별 분기 각도 동작 확인 | 5/6 | 없음 |
| E-05 | C | Python UI 안내창 구현: 분류 결과 + confidence + 쓰레기 적재량 + 가득 참 경고 표시 | 현장 사용자가 앱 없이도 분류 상태와 비움 필요 여부를 즉시 알아야 함 | 로컬 UI 모듈 + `DisplayC` 연동 | `OutputM.handleClassification()` 호출 시 UI 표시 갱신, 센서 full 상태에서 경고 표시 | 5/12 | E-03 |
| E-06 | B + C | Pi BLE Notify 전송 + Android 앱 수신/알림 표시 구현 | 원격 사용자에게 상태 전달하는 MVP 핵심 경로 | BLE 송신 코드 + Android 수신/알림 | Pi 이벤트 발생 시 휴대폰 알림 배너 표시 | 5/12 | E-03 |
| E-07 | C | 최소 통합 검증 1건 작성/실행 (`센서->분류->모터->Python UI->BLE->앱`) | 전체 플로우 작동 증빙 필요 | 통합 테스트/체크리스트/증적 | 실기 로그 + UI 스크린샷/영상 + `pytest` 결과 + PR 첨부 완료 | 5/15 | E-01,E-02,E-04,E-05,E-06 |

## Python UI 안내창 요구사항 (E-05)

- 목적
  - Raspberry Pi에 연결된 화면에서 사용자가 현재 분류 결과와 쓰레기통 상태를 즉시 확인한다.
  - Android BLE 알림은 보조 채널이며, 현장 피드백은 Python UI가 담당한다.
- 표시 항목
  - 최근 분류 라벨: `Can`, `Plastic`, `Glass`, `Paper`, `Unknown`
  - confidence 값
  - 쓰레기 적재량: `SensorC.checkFillLevel()`을 0~100%로 환산
  - 상태 문구: 인식 대기, 분류 완료, 분류함 가득 참, 장치 예외
- 연동 지점
  - `src/hardware.py`의 `DisplayC`를 실제 Python UI 창으로 확장하거나 별도 UI 클래스로 위임한다.
  - `src/output_mgr.py`의 `OutputM.handleClassification()`에서 분류 결과 처리 후 UI를 갱신한다.
  - `OutputM.checkBinFull()` 결과가 true이면 UI 경고와 BLE `BIN_FULL` 이벤트가 함께 발생해야 한다.
- 완료 기준
  - UI 창이 실행 중에도 분류 루프가 멈추지 않는다.
  - 센서 값을 읽을 수 없을 때 프로그램이 종료되지 않고 "적재량 확인 불가"를 표시한다.
  - `--test-mode --test-dispatch`에서 실제 장비 없이 UI 갱신 흐름을 검증할 수 있다.

## 작업 상세 반영 (E-02, E-04)

### E-04 서보 PWM 실동작 + 라벨별 분기
- 목표
  - 모터 제어를 `print`에서 실제 PWM 호출로 교체
  - 분류 라벨별로 서로 다른 각도(`CAN/PLASTIC/GLASS/PAPER/UNKNOWN`)로 회전 반영
- 수정 파일
  - `src/hardware.py`
  - `src/output_mgr.py`
- 테스트 파일
  - `tests/test_hardware_uml.py`
  - `tests/test_output_mgr.py`
- 완료 기준
  - 실기에서 0도/90도 회전 재현
  - 라벨별 분기 각도 동작
  - `UNKNOWN`은 안전 기본각 동작

### E-02 초기화 실패/안전 종료 + 프레임 재시도
- 목표
  - 카메라/모델 실패 시 안전 종료 + `release` 보장
  - `frame is None` 일시 실패 시 즉시 종료하지 않고 재시도 후 임계 초과 시 종료
- 수정 파일
  - `src/main.py`
  - `src/inference.py`
- 테스트 파일
  - `tests/test_camera.py`
  - `tests/test_inference.py`
  - `tests/test_integration_flow.py`
- 완료 기준
  - 초기화 실패 시 리소스 누수 없이 종료
  - 프레임 1~2회 실패 후 복구 시 루프 계속
  - 연속 실패 임계치 초과 시에만 종료

## 제외 작업 (다음 스프린트)
- env 설정 로더 (`CONF_THRESHOLD`, `CONF_CONSECUTIVE`, `PREDICTION_STRATEGY`)
- 대규모 구조 분리 (`src/mobile`, `src/sensors` 리팩터)
- 전 모듈 `print -> logging` 일괄 전환
- 오디오 고도화(TTS/효과음 세분화)
- 고급 테스트 확장(다수 실패 시나리오, 플래키 대응 등)
- 웹 대시보드/원격 관리자 페이지

## 역할 분배
- A: E-01, E-02
- B: E-03, E-04, E-06(송신)
- C: E-05(Python UI), E-06(앱 수신), E-07

## 마일스톤
- M1 (5/2): E-01, E-02, E-03 완료
- M2 (5/12): E-04, E-05, E-06 완료
- M3 (5/15): E-07 완료 및 최종 PR 제출
