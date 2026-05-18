# CONTRIBUTING

이 문서는 EcoSort-AIoT 팀원 4명이 동일한 방식으로 개발하고 리뷰하기 위한 협업 기준입니다.

## 1) 목적 / 적용 범위

- 이 규칙은 본 저장소의 모든 코드 변경(`src/`, `tests/`, 문서 포함)에 적용합니다.
- 모든 변경은 아래 순서를 따라야 합니다: 테스트 통과 -> PR 생성 -> 리뷰 승인 -> 머지.

## 2) Git Flow 규칙

- 기본 브랜치는 `main`입니다.
- 기능 개발은 반드시 `feature/<name>` 브랜치에서 진행합니다.
- `<name>`은 영문 소문자 `kebab-case`를 권장합니다.
- 예시: `feature/add-local-analytics`
- 1 기능 = 1 브랜치 원칙을 지킵니다.
- `main`에 직접 커밋하는 것은 금지합니다.

## 3) Test-First Policy

- 코드 수정 시 PR 생성 전에 `tests/` 단위 테스트를 모두 통과해야 합니다.
- Python UI, BLE, 센서, 모터처럼 실제 장비가 필요한 변경은 가능한 범위의 단위 테스트와 함께 수동 검증 로그를 남겨야 합니다.
- 테스트 실행 예시:

```bash
python -m pytest tests/
```

- **테스트 실패 상태에서는 PR을 올릴 수 없습니다.**

## 4) Commit Message Convention

- 형식: `<type>: <summary>`
- 허용 접두어:
  - `feat:` 새로운 기능
  - `fix:` 버그 수정
  - `docs:` 문서 수정
  - `test:` 테스트 추가/수정
- 커밋 제목은 영문을 권장합니다.

좋은 예시:
- `feat: add waste label validation`
- `fix: handle empty detection result`

나쁜 예시:
- `update code`
- `fix stuff`

## 5) Code Review & Merge Rule

- PR은 작성자 본인을 제외한 최소 1명 이상의 승인을 받아야 머지할 수 있습니다.
- 승인 전 self-merge는 금지합니다.
- 리뷰 요청사항이 있으면 반영 후 재리뷰를 요청해야 합니다.

## 6) PR 제출 체크리스트

- [ ] `tests/` 단위 테스트를 통과했다.
- [ ] 변경 내용을 PR 본문에 요약했다.
- [ ] 리뷰어가 봐야 할 핵심 포인트를 작성했다.
- [ ] 관련 이슈/작업 항목이 있으면 링크했다.
- [ ] Python UI 안내창 변경이 있으면 분류 라벨, confidence, 적재량, 가득 참 경고 표시를 스크린샷/영상으로 검증했다.
- [ ] 센서/모터/BLE 변경이 있으면 실제 장비 또는 명시한 stub 환경에서 검증 로그를 첨부했다.

## 7) UI 변경 기준

- Python UI 안내창은 현장 사용자가 보는 1차 피드백 채널입니다.
- UI는 최소한 최근 분류 결과, confidence, 쓰레기 적재량, 경고 상태를 표시해야 합니다.
- 센서 읽기 실패나 BLE 연결 실패가 있어도 UI 프로세스가 함께 종료되면 안 됩니다.
- 테스트 모드(`--test-mode --test-dispatch`)에서 UI 갱신 흐름을 재현할 수 있어야 합니다.
