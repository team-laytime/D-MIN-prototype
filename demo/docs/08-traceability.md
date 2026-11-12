# 08. 요구사항 추적표 — 무엇을, 어디서, 어떻게 확인했나

- 작성 2026-11-09 · 기준: 팀 구글 문서 '[판교_2반_1조] 프로젝트정의 요구사항서' **(최종) 탭** 3절(FR-01~52, NFR-01~21). 같은 문서의 '요구사항 목록(통합안)' 탭은 번호가 다르니 주의(예: 통합안 FR-25 = 최종 FR-24).
- 상태: ✔ 구현하고 시험으로 확인 · △ 일부만 · ✘ 아직 안 함
- 확인 방법: GC = 정답 세트(`data/golden`), T = 테스트(`tests/`), S = 시나리오, 화면 = 직접 눌러 봄
- v0.2(같은 날 오후) 갱신: 계약서 23건·시나리오 16개·업무형 화면 반영, 질의응답 Agent 제외(ADR-012). 바뀐 줄: FR-01·26·30·37·39·52, NFR-03·15·16

## 기능 (FR)

| ID | 요구사항(짧게) | 우선 | 상태 | 어디서 | 확인 |
|---|---|---|---|---|---|
| FR-01 | 시나리오 입력(파일·화면) | Must | △ | `engine/intake.py`, 화면 '입항 예정 선박' | 시나리오 16개 + 검증 4개 로드, 화면에서 ETA를 고쳐 수정본으로 다시 계산. **CSV·XLSX 템플릿은 아직 JSON만** |
| FR-02 | 입력 검증 | Must | ✔ | `intake.py` | T `test_input_errors_stop_before_calculation` 10건 |
| FR-03 | 기준 정보 관리 | Must | ✔ | `data/master/terminal_ulsan_clx.v1.json` | 제원·화물 그룹·Direction·Switching·조합·야간 도선·Daylight 선종 |
| FR-04 | 과거 작업 실적 | Should | ✔ | `data/history/shipments.v1.csv` | GC-11 |
| FR-05 | 일출·일몰 | Must | ✔ | `data/providers.py`, `solar.py` | 시나리오 값 → 저장본 → NOAA 계산(값이 빠지는 날이 없음) |
| FR-06 | 공공데이터 연동 | Should | △ | `fetch-public` 명령, 제공자 구조 | 서비스키가 없어 **API 호출은 안 함**, 출처·수집 시각 표시 |
| FR-07 | 부두 제원 적합성 | Must | ✔ | `eligibility.py` | GC-10(항목 5종 + 수출선 Draft 제외 + 복합) |
| FR-08 | 화물 그룹 적합성 | Must | ✔ | `eligibility.py`, `cargo_groups.v1.json` | GC-10 자재코드 10개 + 미등록 코드 오류 |
| FR-09 | 선행 선박 반영 | Must | ✔ | `etb.py` ETB-01 | GC-01, GC-07 |
| FR-10 | FIX 선박 보호 | Must | ✔ | `etb.py` ETB-02, `validator.py` | GC-08(같은 시각 경계), T 시나리오마다 FIX 불변 |
| FR-11 | 선박 상태 반영 | Should | ✔ | `context.py` | WORKING·FIX 불변, COMPLETED 제외(S1~S5) |
| FR-12 | 야간 도선 제한 | Must | ✔ | `etb.py` ETB-03·04 | GC-04 10사례(Last POB 정각·02:00·08:00 경계) |
| FR-13 | 동일 화물 그룹 동시 접안 | Must | ✔ | ETB-05 | GC-05 3사례 |
| FR-14 | 부두 동시 접안(#4) | Must | ✔ | ETB-06 | GC-06(GRT 3,000 경계) |
| FR-15 | 부두 사용 제한 | Must | ✔ | ETB-07 | GC-07(하역 중 선박 계속 작업) |
| FR-16 | 재고 제약 | Must | ✔ | ETB-09 | GC-14(날짜·그룹·부족량 표시) |
| FR-17 | 조석 제약 | Must | ✔ | ETB-08 | GC-15 |
| FR-18 | 출하 마감·우선 배정 | Could | △ | ETB-11, `priority: URGENT` | 마감은 하드 제약(T 후보 없음 시험), 우선 배정은 리스크 점검에만 씀 |
| FR-19 | 임시 조건 추가 | Could | △ | `allowed_berths` | 부두 지정·금지만. 'A는 B보다 먼저'는 없음 |
| FR-20 | ETB 통합 산정 | Must | ✔ | `etb.py` 밀어내기 반복 | GC-07·13·15(제약 2개 이상 겹침) |
| FR-21 | 제약 켜고 끄기 | Could | ✘ | (규칙 표 patch로 값만 바꿀 수 있음) | 다음 |
| FR-22 | 작업 시각 산정 | Must | ✔ | `worktime.py`, `etb.make_placement` | GC-01 네 시각 |
| FR-23 | 작업시간 추정 | Should | ✔ | `worktime.py` | GC-11(1차·2차·실적 없음, 근거에 단계·건수) |
| FR-24 | 정박개시(Daylight 미적용) | Must | ✔ | `laytime.py` LAY-02~05 | GC-02 9사례(경계 2개 포함) |
| FR-25 | 정박개시(Daylight 적용) | Must | ✔ | LAY-06 | GC-03 5사례 — PPT 10쪽 없어 [가정] |
| FR-26 | Laytime 적용 | Must | ✔ | 계약서 23건(`data/contracts`), `rules/contracts.py`, `contract_rules.v1.json` 계약 유형 | 계산서 6단계에 계약서 조항 번호(T `test_calc_sheet_cites_contract_clause_numbers`), 부분 화물 비례(T `test_pro_rata_laytime_comes_from_contract`) |
| FR-27 | CFR Plus 특례 | Could | ✔ | 계약 표 `CFR_PLUS` | T `test_cfr_plus_…`('미확정 규칙 포함') |
| FR-28 | 기상 공제 | Must | ✔ | DEM-02 | GC-09·13(공제 전·후 표시) |
| FR-29 | 선박별 예상 체선료 | Must | ✔ | DEM-03 | 정답 세트 전 사례 |
| FR-30 | 시나리오 합계 | Must | ✔ | `schedule.evaluate`, `views.complete` | 합계 = 선박별 합(차이 0, 실행 검사). 배정 못 한 배가 있으면 '성립 안 함'과 그 배·사유 표시, 절감액 계산 안 함(S15, T `test_baseline_that_breaks_a_deadline_is_reported_not_compared`) |
| FR-31 | 단일 선박 계산 | Should | ✔ | 한 척 시나리오(API·CLI) | GC-02·03 |
| FR-32 | 체선 사유 분해 | Should | ✔ | `laytime.reason_breakdown` | 합 = 공제 전 체선 시간, '미상' 칸 |
| FR-33 | 규칙 해석 대안 계산 | Could | ✘ | — | 다음(규칙 patch로 수동 비교만) |
| FR-34 | 기준안(FCFS) | Must | ✔ | `schedule.fcfs` | GC-01·12, '비교용 기준안(현행 실적 아님)' 표시 |
| FR-35 | 후보 생성(최대 3개) | Must | ✔ | `optimizer.py` | 위반 0, 1척 이상 다름, '개선 없음'·'최선 탐색 결과' 표시(T) |
| FR-36 | 후보 없음 처리 | Should | ✔ | `NO_FEASIBLE` | T `test_no_feasible_candidate_is_reported` |
| FR-37 | 부두별 타임라인 | Must | ✔ | 화면 간트(`web/app.js`), 보고서 SVG(`report/timeline.py`) | 작업·준비·체선·대기·강풍·정비·야간·조석을 한 그림에, 막대를 누르면 계산서 |
| FR-38 | 후보 비교표 | Must | ✔ | `report/views.py` | 총액 = 선박 합, 증감 합 = 절감액(실행 검사) |
| FR-39 | 산출 근거 조회 | Must | ✔ | `laytime.calc_sheet`, `/vessels/{안}/{선박}` | 계산서 9단계(식 + 근거 칩: 계약 조항·운영 기준·부두 기준·입력·실적), 계약 칩은 조항으로 이동(화면), T API·조항 인용 |
| FR-40 | 남은 리스크 점검(5항목) | Must | ✔ | `engine/risk.py` | 모든 후보 5항목, 데이터 없으면 '판단 불가' |
| FR-41 | 대안·주의 문구 | Must | ✔ | `risk_phrases.v1.json` | 단정 표현 0건(T) |
| FR-42 | 리스크 확인 표시 | Could | △ | 확정 시 경고만 | 항목별 '확인함' 체크는 없음 |
| FR-43 | 입력 변화 민감도 | Must | △ | `sensitivity.py` | ETA ±6h·예보 4가지 계산·표시. **손계산 대조는 아직** |
| FR-44 | 보고서 초안 | Must | ✔ | `report/builder.py` | 숫자 대조 0건, '담당자 검토용 초안' |
| FR-45 | 메일 초안 | Must | ✔ | `render_mail` | 발송 기능 없음 |
| FR-46 | 편집·내려받기 | Should | ✔ | .md·.docx·.csv, 메일 편집 | T API(.docx·CSV 한글) |
| FR-47 | 후보 확정(덧붙이기) | Must | ✔ | `/decisions`, DB 트리거 | T SQLite, 컨테이너 Postgres |
| FR-48 | 후보 상태 표시 | Should | ✔ | `candidate_states` | 추천 → 선택됨 → 현업 반영 완료 |
| FR-49 | 검증 시나리오 | Must | ✔ | `data/scenarios/`, `validation/` | 통합 시나리오(강풍 + 집중) 포함 |
| FR-50 | 검증 일괄 실행 | Must | ✔ | `verify --strict`, 화면 7단계 | 불일치 시 기대·실제·규칙 ID |
| FR-51 | 최적성 검증 | Should | ✔ | `brute_force` | 시나리오 4/4 + 무작위 80사례 |
| FR-52 | 업무 단계 안내 | Should | △ | 화면 사이드바(업무 순서로 6묶음) | 단계 잠금은 없앰 — 첫 화면에서 대표 시나리오를 바로 계산하고, 계산 전 화면은 '계산 결과가 없습니다' 안내 |

## 비기능 (NFR)

| ID | 요구사항(짧게) | 우선 | 상태 | 확인 |
|---|---|---|---|---|
| NFR-01 | 계산 결정성(LLM은 문장만) | Must | ✔ | T AST 검사: engine·domain·rules에 LLM import 0 |
| NFR-02 | 재현성 | Must | ✔ | T 10회 같은 지문, 실행마다 입력·규칙·엔진·탐색 설정 저장 |
| NFR-03 | 근거 추적성 | Must | ✔ | 보고서·메일 숫자 대조 불일치 0(S05: 345 + 77개), 계산서 근거에 계약 조항 번호 |
| NFR-04 | 규칙 분리·버전 | Must | ✔ | GC-09 시연 2종, T 이전 규칙으로 다시 → 같은 결과 |
| NFR-05 | 규칙 ID 추적 | Should | ✔ | T 코드·정답 세트의 ID가 규칙 표에 모두 있음 |
| NFR-06 | 시간·금액 처리 | Must | ✔ | T 자정·월말, 센트 정수 |
| NFR-07 | 결과 상태 표시 | Should | △ | '가정값 포함·미확정 규칙 포함·확인 필요 규칙 포함', '가상 데이터·의사결정 보조용' 문구. '데이터 누락' 라벨은 없음 |
| NFR-08 | 성능(8척 30초) | Should | ✔ | 0.06초, 보고서 0.01초 |
| NFR-09 | 확장성(12척 60초) | Should | ✔ | 12척 18초 최적 증명, 16척 30초 최선 탐색(갭 78.9%) |
| NFR-10 | 외부 장애 대응 | Should | ✔ | LLM·공공데이터 없이 완주, 화면에 '템플릿 사용' |
| NFR-11 | 오류 시 입력 보존 | Should | ✔ | T 422 + 입력 그대로 |
| NFR-12 | LLM 비용 관리 | Should | ✔ | T 상한 초과 → 호출 0, 템플릿 |
| NFR-13 | 비밀정보 관리 | Must | △ | `.env` 제외·예시 파일, CI gitleaks(로컬에서는 미실행) |
| NFR-14 | LLM 전송 데이터 제한 | Should | ✔ | T 선박명·비고·요율 없음 |
| NFR-15 | 프롬프트 주입 방어 | Should | ✔ | T 숫자 섞인 LLM 문장 거절, LLM 입력에 선박명·비고(자유 입력) 없음. 질의응답 창은 v0.2에서 뺌 |
| NFR-16 | Agent 권한 제한 | Must | ✔ | 처리 단계 동작 목록에 쓰기 0, 확정은 `POST /decisions` 하나(화면 확정 창, 담당자 이름·리스크 확인 필수) |
| NFR-17 | 실행 이력 로그 | Should | ✔ | `agent_log`, `audit_events`, JSON 로그(키·요율 원문 없음) |
| NFR-18 | 변경 용이성 | Should | ✔ | 모듈 경계(01 문서), LLMClient 인터페이스 |
| NFR-19 | 변경 안전성 | Should | △ | CI 파일 작성·같은 단계 로컬 통과, 계산·제약 모듈 커버리지 88~97%. **GitHub에서 실제 실행은 아직** |
| NFR-20 | 사용성(10분 완주) | Could | ✘ | 평가자 시험 안 함 |
| NFR-21 | 사용 환경(Chrome·Edge, 1366×768) | Should | △ | 내장 브라우저(Chromium)에서 확인, Edge·실제 해상도 시험은 안 함 |

## 요약

| 우선순위 | 개수 | ✔ | △ | ✘ |
|---|---|---|---|---|
| Must | 42 (FR 35 · NFR 7) | 39 | 3 — FR-01 CSV·XLSX 템플릿, FR-43 손계산 대조, NFR-13 비밀 검사 실제 실행 | 0 |
| Should | 24 (FR 11 · NFR 13) | 19 | 5 — FR-06 공공데이터 API, FR-52 단계 잠금 없앰, NFR-07 '데이터 누락' 라벨, NFR-19 GitHub 실행, NFR-21 Edge·해상도 | 0 |
| Could | 7 (FR 6 · NFR 1) | 1 | 3 — FR-18, FR-19, FR-42 | 3 — FR-21, FR-33, NFR-20 |
