# 화면 ↔ 서버 계약 (초안)

프로토타입은 `js/core/api.js`가 이 계약을 브라우저 안에서 흉내 낸다. Spring 서버가 생기면 그 파일의 함수 몸통만 `fetch`로 바꾸고 화면 코드는 그대로 둔다. 계산 결과의 모양은 수리계획법 응답(`docs/milp/ppt/README.md` 6절, `run.optimize`)과 같다 — `console/data/run.json`이 그 응답에서 왔다.

모든 시각은 KST `YYYY-MM-DDTHH:mm`, 금액은 USD(소수 둘째 자리, 내부는 센트 정수)다 (NFR-07).

## 선박 · 일정 (조회)

| 메서드 · 경로 | 화면 | 돌려주는 것 |
|---|---|---|
| `GET /api/v1/vessels` | 대시보드 · 선박 지도 · 입항 예정 선박 | 선박마다 신원(MMSI · IMO · 호출부호 · 제원), `ais`(위치 · SOG · COG · 항행 상태 · 수신 시각 · 출처 · 목적지 원문 · AIS ETA), `port_mis`(입항연도 · 항차 · 시설 신청/배정/사용), `plan`(적용 버전의 부두 · ETB · ETU · 호스분리 · 체선료), `eta_diff_min`, `needs_recalc` |
| `GET /api/v1/schedule?from&to` | Berthing Schedule | `version`(번호 · 이름 · 승인 시각 · 승인자 · 실행 ID · 입력 기준 · 규칙 · 엔진 버전) + 행(부두 · ETA · ETB · ETU · Biz · Shipment · 선박 · 제품 · 수량 · 호스분리 · 대기 · 체선료 · 상태 · 이전 버전 값) |
| `GET /api/v1/schedule/versions` | ETB Change Log · 승인·적용 기록 | 버전 목록. 버전 사이 변경은 `GET /api/v1/schedule/versions/{no}/diff` |
| `GET /api/v1/alerts/eta` | 대시보드 · 계획 · 보고서 · 승인 | AIS ETA와 계획 입력 ETA가 기준(2시간)보다 크게 다른 선박 |
| `GET /api/v1/sources/status` | 대시보드 '데이터 연계 상태' | 연계별 마지막 수신 시각 · 상태 · 주기 |

## 후보 계산

| 메서드 · 경로 | 내용 |
|---|---|
| `POST /api/v1/optimizations` | 본문 `{plan_window, options}` → `202 {job_id, request_hash}`. Spring이 업무 DB에서 입항 건 · 계약 · 부두 제약을 모아 Python 서비스에 넘긴다. 같은 `request_hash`면 저장된 결과를 돌려준다 (NFR-02) |
| `GET /api/v1/optimizations/{job_id}/events` | SSE. `{step, total, name, detail}`이 단계마다, 끝나면 `{done: true, run_id}` |
| `GET /api/v1/runs/{run_id}` | `run.optimize` 응답 그대로: `engine` · `baseline` · `current_plan` · `candidates[]`(선박별 `plans`와 규칙 ID가 붙은 `trace`) |

## 보고서 · 승인

| 메서드 · 경로 | 누가 | 내용 |
|---|---|---|
| `POST /api/v1/reports` | 접안 계획 담당 | `{run_id, recommended}` → `{id, status: "draft"}`. 문장은 LLM 초안(응답 없으면 템플릿), 숫자는 계산 결과 참조 |
| `POST /api/v1/reports/{id}/submit` | 접안 계획 담당 | `{note}` → `status: "requested"` |
| `POST /api/v1/approvals/{report_id}` | **승인권자만** | `{action: "approve" \| "reject", candidate, reason, reason_type, risks_checked[], stale_ack}` → 승인이면 새 `version`. 다른 역할은 `403`. Agent 도구 목록에는 이 호출이 없다 (NFR-17) |
| `GET /api/v1/audit` | 승인권자 | 덧붙이기만 하는 기록 (사람 · 역할 · 동작 · 대상 · 내용 · 시각) |

## 정할 것

- 승인 후 PORT-MIS 시설 배정에 반영하는 방법 (사람이 PORT-MIS에 넣는지, 연계하는지) — 화면은 '반영할 목록'까지만 만든다.
- 동률일 때 2차 기준을 기준안 대비로 볼지 현행 계획 대비로 볼지 (샘플에서 둘의 순서가 다르다).
- 역할 이름과 권한 (스케줄러 · 승인권자 · 조회)과 로그인 방식.
