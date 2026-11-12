# CLOCK — 레이타임 계산 엔진 프로토타입

- 작성일: 2026-11-02 · 데이터는 전부 **가상**(문서 `04` 예제)이고 규칙값 일부는 [가정]이다.
- 한 줄: **06 표준 SOF 이벤트 + 계약 조건 → 레이타임 계산서**(개시·공제·반액·종료·체선 시간·금액). 계산서 줄마다 룰 ID와 SOF 행 번호가 붙는다. `05` §7 쟁점은 판정하지 않고 "담당자 확인 필요"로 올리고 대안 계산을 함께 낸다.
- 결과: `docs/domain/04` **TC-01~05·TC-01b·TC-05b 정답 전부 일치**. 테스트 122개 통과. 검증하며 찾은 문서 보완 10건은 같은 날 `docs/domain`에 반영했다(§9).
- 표기: [사실] / [추론] / [추천] / [가정] / [확인 필요] (`docs/domain/00-README.md` §3).

---

## 1. 스택과 선택 이유

| 항목 | 선택 | 근거 |
|---|---|---|
| 언어 | Python 3.11+ | 팀 문서에 CLOCK의 언어를 정한 곳이 없다 [사실, `docs/` 전체 검색]. `../docs/seagate-handoff.md` §5-5의 아키텍처 제안(Spring Boot API + **Python** LangGraph 에이전트 + Python FastMCP)과 같은 날 만든 `../prototype/`(Python 표준 라이브러리)이 모두 Python 쪽이라 맞췄다 |
| 엔진 의존성 | 표준 라이브러리만(외부 패키지 0) | 결정론. LLM·네트워크 호출 없음 |
| 테스트 | pytest | 브리프 지정. 개발 의존성만 |
| 숫자 | 시각 = 기준 시각부터의 분(`Fraction`), 금액 = 센트 반올림(ROUND_HALF_UP, 정수 연산) | 부동소수점 오차 없이 같은 입력 → 같은 출력 |

계산 코어를 나중에 Spring Boot 쪽에 둘지 Python 에이전트 서비스에 둘지는 정해지지 않았다 [확인 필요]. 엔진은 JSON 입출력이라 어느 쪽에서든 감싸 쓸 수 있다.

---

## 2. 실행

```bash
cd clock
```

테스트(pytest가 없으면 `python3 -m pip install pytest`):

```bash
python3 -m pytest
```

전체 케이스 요약표:

```bash
python3 -m laytime
```

계산서 한 장(Markdown), JSON(06 LAYTIME_STATEMENT 필드명):

```bash
python3 -m laytime cases/TC-03.json
```

```bash
python3 -m laytime cases/TC-03.json --json
```

코드에서:

```python
from laytime import load_case, compute_statement, render_markdown

st = compute_statement(load_case("cases/TC-03.json"))
st.amount_usd, st.demurrage_hours, [i.code for i in st.issues]
print(render_markdown(st))
```

---

## 3. 결과 — 문서 정답 대조

| TC | 핵심 규칙 | 문서 정답 (체선 / USD) | 엔진 | 문서가 요구한 플래그 → 엔진 이슈 |
|---|---|---|---|---|
| TC-01 | 개시 = min(NOR+6h, all fast) | 0 / 0 | 0h 00m / 0.00, 여유 30m | 여유 30분 경고 → `LOW-MARGIN` [경고] |
| TC-01b | 개시 후 이동 공제 | 3h 30m / 17,500 | 3h 30m / 17,500.00 | 야간 금지 대기의 부담 주체 → `DISPUTE-NIGHT-WAIT` [담당자 확인 필요], 대안 0.00* |
| TC-02 | 대기 산입, 이동 공제 | 3h 00m / 6,875 | 3h 00m / 6,875.00 | — → 이슈 없음 |
| TC-03 | 묘박지 체선 돌입, once on demurrage, 반액 | 40h 30m (34.5 + 반액 6) / 187,500, 대안 177,500 | 40h 30m (34h 30m + 6h) / 187,500.00, 대안 177,500.00 | 체선 중 이동 → `DISPUTE-SHIFT-ON-DEM`, 야간 계류 금지 대기 → `DISPUTE-NIGHT-WAIT` 대안 117,500.00(문서 계산표: 선석 전환 0 가정) |
| TC-04 | 펌핑 워런티 공제 | 0 / 0 (공제 없으면 7,292) | 0 / 0.00, 대안 7,291.67 | 육상 제한 없음 입증 → `PUMPING-EVIDENCE` [증빙 확인] |
| TC-05 | 무효 NOR | 0 / 0 (선주 3h 30m / 3,792) | 0 / 0.00, 대안 3h 30m / 3,791.67 | 조기 NOR, waiver → `NOR-EARLY` [증빙 확인] + `DISPUTE-NOR-WAIVER` [담당자 확인 필요] |
| TC-05b | 무효 NOR 후 재제출 | 1h 30m / 1,625 | 1h 30m / 1,625.00 | 조기 NOR, 첫 NOR 수령의 waiver → `NOR-EARLY` + `DISPUTE-NOR-WAIVER`, 대안 3,791.67* |

\* 엔진 산출값 — 문서에 정답이 없다. 테스트에서도 문서 정답(`tests/test_golden_tc.py`)과 분리해 `tests/test_engine.py`에서 검증한다.

- **어긋난 TC 없음.** 문서의 계산도 손으로 다시 따라가 모두 맞는 것을 확인했다(경과·공제·체선 개시·금액).
- 금액: 문서는 달러 단위로 반올림해 적었다(7,291.67 → 7,292, 3,791.67 → 3,792). 엔진은 센트까지 내고, Golden 테스트는 센트를 달러로 반올림해 비교한다.
- 교차 검증: 같은 TC를 `../prototype/engine/clock.py`(별도 구현)로 돌려 기본 계산·문서 대안이 전부 같은 값임을 확인했다(§10).

---

## 4. 입력 — 케이스 JSON (`cases/*.json`)

| 블록 | 내용 | 06과의 관계 |
|---|---|---|
| `contract_terms` | `form`, `layer`, `laytime_this_port_hours`(허용), `notice_hours`, `demurrage_rate_usd_day`, `half_rate_events`, `pumping_warranty_hours`·`_psi`, `shifting_counts_on_demurrage`(YES·NO·DISPUTED, 없으면 DISPUTED) | 06 §5 CONTRACT_TERMS 필드명 그대로 |
| `sof_events[]` | `event_id`, `row`(SOF 원문 행), `event_type`, `ts_local`, `source`, `remarks`, `evidence_ref`, `confidence` | 06 §6 SOF_EVENT 그대로. event_type은 06 표준 목록만 받는다 |
| └ `reason_code` | OPS_STOPPED 사유(WEATHER·SHORE_TANK·SHIP_EQUIPMENT·SHORE_EQUIPMENT·DOCUMENTS·SAFETY·STRIKE·FIRE·EXPLOSION·OTHER) | 06 §6 `reason_code` |
| `terminal` | `berth_ready_at`(선석이 빈 시각 = 앞 선박 이안) + `berth_ready_row`·`_ref`, `berthing_rules`(예 `ULS-SBM-NIGHT`), `daytime`(07:00~17:30) | `berth_ready_at`은 06 §9 BERTH_PLAN. 나머지는 **확장**(BERTH 룰, ULS-DAYTIME-DEF). 대기 사유(선석 점유 / 야간 제한 / 기타 / 미상)를 가른다 |
| `pumping_log` | `avg_manifold_psi`, `shore_restriction`, `source`, `evidence_ref`, `sof_rows` | 06 §6 PUMPING_LOG. 계산서 근거용 `sof_rows`만 **확장** |
| `port_call.operation` | DISCHARGE · LOAD | 06 §4 PORT_CALL |
| `expected`, `doc_rows_not_events` | 문서 정답과 출처, 입력에서 뺀 문서 행 | 테스트 전용. 엔진은 읽지 않는다 |

- 시각: `"D1 08:00"`(D1 = `base_date`, D0 = 전날 — 문서 표기 그대로) 또는 ISO 8601 현지시각(`2026-11-03T08:00+09:00`). +09:00이 아닌 오프셋은 거부한다(UTC 변환은 INTAKE 몫, 06 머리말).
- SOF 행 번호는 `04` SOF 표의 행 순서다(계산 행 포함, `04` 머리말). *(계산)* 행(통지시간 만료·레이타임 개시·체선 개시)은 입력에서 빼고 `expected`로 옮겼고, *(선석 가용)* 행(TC-03 3행 앞 선박 이안)은 `terminal.berth_ready_at`(행 3)으로 옮겼다.
- 검증: 알 수 없는 이벤트·사유 코드, 필수 이벤트(NOR·ALL_FAST·HOSES_DISCONNECTED) 누락, 시각 순서 역전, 짝 없는 하역 중단, 같은 이벤트 2회(재투묘·선석 이동·재접안 — 미지원)는 `CaseError`로 **계산하지 않고 멈춘다**.

## 5. 출력 — 계산서 (`Statement`, `to_dict()`)

- 06 §7 LAYTIME_STATEMENT 필드명: `nor_received_at`, `notice_expiry_at`, `all_fast_at`, `laytime_start_at`, `start_rule`, `laytime_end_at`, `end_rule`, `deductions[]`(06 DEDUCTION: `from_ts`·`to_ts`·`hours`·`category`·`rule_id`·`evidence_ref`·`disputed`), `used_hours`, `allowed_hours`, `demurrage_hours`, `demurrage_start_at`, `half_rate_hours`, `amount_usd`, `alt_calculations[]`, `issues[]`, `version`, `computed_at`, `rules_version`.
- 추가: `lines[]` — `04` §0 템플릿 순서의 계산서 줄. **줄마다 `rule_ids`와 `sof_rows`**, SOF 밖 근거(허용 시간·요율 등 계약 필드)는 `source`. `ledger[]` — 구간 원장(개시 전·레이타임·체선·종료 후 × 산입·공제·전액·반액·미산입, 구간마다 룰 ID·SOF 행).
- `computed_at`은 엔진이 비워 두고 CLI `--json`이 채운다(같은 입력이면 같은 출력이 되게).

## 6. 계산 규칙 (`laytime/engine.py`, `docs/domain/03` §2·§6)

| 단계 | 규칙 | 룰 ID |
|---|---|---|
| 개시 | min(NOR 수령 + 통지시간, 접안 완료). NOR 전에는 개시하지 않음 | ASB-06-NOR-START |
| 무효 NOR | 투묘 전 제출이면 무효 → 재제출 NOR 기준, 재제출이 없으면 하역 개시 | LAW-NOR-ARRIVAL, LAW-NOR-WAIVER |
| 대기 | 개시 후 묘박 대기는 산입. 사유를 선석 점유·야간 제한·기타·미상으로 표시 | ASB-09-REACHABLE (+ ULS-SBM-NIGHT 등) |
| 이동 | 레이타임 중 양묘~접안 완료는 공제. 체선 중은 계약 `shifting_counts_on_demurrage`대로(DISPUTED면 산입 + 쟁점) | ASB-07-SHIFTING-EXCL, LAW-ONCE-ON-DEM |
| 선박 귀책 | OPS_STOPPED `SHIP_EQUIPMENT`는 공제 | ASB-07-VESSEL-FAULT |
| 펌핑 | 실하역(중단 제외) > 보증 시간이고, 평균 압력 < 보증 psi, 육상 제한 없음 기록이 있으면 초과분 공제. 하역 끝에서부터 잘라낸다 | RIDER-PUMPING |
| 반액 | 체선 중 OPS_STOPPED 사유가 계약 `half_rate_events`에 해당하면 반액 | ASB-08-HALF-RATE |
| 종료 | 호스 분리 | ASB-11-END-HOSES |
| 금액 | 전액시간 × 율/24 + 반액시간 × 율/48 | ASB-08-RATE-PRORATA |
| 경고 | 체선이 없어도 여유 2h 미만 | ENG-LOW-MARGIN |

사용 시간 = 경과 − 공제, 체선 = max(0, 사용 − 허용), 체선 = 전액 + 반액. 이 합계 불변식을 엔진이 매번 확인하고(어긋나면 `AssertionError`), 테스트가 모든 케이스·대안에서 다시 확인한다.

## 7. 쟁점 처리 — `05` §7 (자동 판정 금지)

기본 계산은 **`04` 정답과 같은 기준**이고, 쟁점마다 반대 입장의 대안 계산을 붙인다. 이슈 등급은 모두 `담당자 확인 필요`.

| §7 | 쟁점 | 감지 조건 | 기본 계산 | 대안 계산 | 이슈 코드 | 상태 |
|---|---|---|---|---|---|---|
| 1 | 체선 중 이동 | 이동이 체선 중 + 계약 DISPUTED | 산입(TC-03 정답) | 공제 | `DISPUTE-SHIFT-ON-DEM` | 구현 |
| 2 | 야간 접안 제한 대기의 부담 주체 | 선석이 빈 뒤에도 대기했고, 그때 움직였다면 접안 완료가 주간 창 밖 | 산입(TC-01b 정답) | 레이타임 중 해당 대기 불산입(cl.6 예외) | `DISPUTE-NIGHT-WAIT` | 야간만 구현. **기상 대기는 미구현**(풍속 입력 필요) |
| 3 | 레이타임 중 폭풍 중단의 반액 | 레이타임 중 반액 사유 중단 + 체선 발생 | 전액 | 체선 앞부분의 같은 시간을 반액 | `DISPUTE-LAYTIME-HALF-RATE` | 구현(04 변형 3b) |
| 4 | 대리점 NOR 수령 = waiver? | 무효 NOR에 수령 기록 | 무효 NOR 기준(TC-05 정답) | 첫 NOR 유효 | `DISPUTE-NOR-WAIVER` | 구현 |
| 5 | 서류 대기 산입 | 호스 분리 후 서류 대기 > 3h [가정] | 미산입(Asbatankvoy) | 3h 초과분 산입 | `DISPUTE-DOCS-WAIT` | 구현 |
| 6 | 매매·용선 레이어 불일치 | 계산서 1장으로는 감지 불가 | — | — | — | **미구현** — CP·SALES 계산서 2장 비교가 필요 |

§7 밖 이슈: `VESSEL-FAULT-ON-DEM`(체선 중 선박 귀책 중단, 담당자 확인 필요) · [증빙 확인] `NOR-EARLY`, `PUMPING-EVIDENCE`, `PUMPING-NO-LOG`, `NOR-NO-RECEIPT`, `NO-ANCHOR-AWEIGH`, `STOP-NO-REASON` · [경고] `LOW-MARGIN` · [참고] `NOR-AFTER-BERTH`, `NOR-MULTIPLE`, `NOR-ARRIVAL-UNKNOWN`, `PUMPING-SHORE-RESTRICTED`, `PUMPING-NO-OPS`.

## 8. 가정 [가정]

| 가정 | 값 | 어디서 바꾸나 |
|---|---|---|
| "주간" | 07:00~17:30, **접안 완료 시각** 기준(문서 TC들이 07:00 전 양묘 + 주간 접안을 정상으로 다룸) | `terminal.daytime` |
| 중단 사유 → 반액 사유 | WEATHER→STORM, SHORE_EQUIPMENT→PLANT_BREAKDOWN, STRIKE·FIRE·EXPLOSION은 그대로 | `model.HALF_RATE_BY_STOP_REASON` |
| 펌핑 초과분 위치 | 하역의 마지막 n시간 | `engine._apply_pumping` |
| 야간 제한 대기의 범위 | 선석이 빈 시각부터 실제 양묘까지 전부. 선석 전환 시간은 두지 않음(prototype은 60분 `PLAN-TURNOVER`) | `engine._after_ready_reason` |
| 서류 대기 쟁점 기준 | 3h (`05` §3의 예시값) | `rules.DOCS_WAIT_GRACE_HOURS` |
| 여유 경고 | 2h (prototype `ENG-LOW-MARGIN`과 같음) | `rules.LOW_MARGIN_HOURS` |
| 체선 중 선박 귀책 중단 | 기본 공제 + 담당자 확인(대안: 산입) | `Policy.vessel_fault_on_demurrage` |
| TC-05·TC-05b 첫 NOR 수령 시각 | 송신 시각(D1 11:00)과 같다고 둠 — 선주 청구 11:00+6h에서 역산 | `cases/TC-05.json`, `cases/TC-05b.json` |

## 9. 검증하며 고친 문서 (2026-11-02 반영)

CLOCK을 만들며 찾은 보완 10건을 `docs/domain`에 반영했다. 정답 숫자는 하나도 바뀌지 않았고, 고친 문서마다 머리에 갱신 줄을 달았다.

| # | 문서 | 바꾼 것 |
|---|---|---|
| 1 | `04` 변형 1b | 도착(투묘)도 D0 20:00으로 명시. 도착 시각이 없으면 NOR 유효성을 판단할 수 없었다 |
| 2 | `04` 예제 3·TC 요약표 | 쟁점 "야간 계류 금지 대기의 부담 주체"(`05` §7-2) 추가. 계산표에 쟁점 행(대안 117,500, 선석 전환 0 가정 / 60분이면 122,500) |
| 3 | `04` SOF 표·머리말 | 계산 결과 행에 *(계산)*, TC-03 앞 선박 이안 행에 *(선석 가용)* 표시. 머리말에 읽는 법과 행 번호 규칙 |
| 4 | `04` 머리말 | 금액 반올림 규칙: 표는 달러 반올림(7,291.67 → 7,292), 엔진은 센트 |
| 5 | `04` 예제 5·TC 요약표 | 재제출 변형에 TC-05b 번호와 정답표 행 |
| 6 | `06` §6 | SOF_EVENT `reason_code` 필드, 사유 코드 STRIKE·FIRE·EXPLOSION, 반액 사유 대응 |
| 7 | `06` §1·§6·§9·§11 | NOR 재제출 표기, PUMPING_LOG 엔티티, BERTH_PLAN `berth_ready_at`, SEAGATE 매핑에 PUMPING_LOG |
| 8 | `05` §2·§2-1·§6 | `ASB-07-HOURS`와 서식 밖 룰 4개(`LAW-NOR-ARRIVAL`·`LAW-NOR-WAIVER`·`LAW-ONCE-ON-DEM`·`ENG-LOW-MARGIN`) 등록. `status` 값을 confirmed·public·verify·assumed·disputed로 통일 |
| 9 | `03` §6 | 펌핑 초과 공제를 사용 시간 계산 앞으로 옮김(`04` §0 템플릿·TC-04와 같은 순서) |
| 10 | `03` §6 | "NOR 수령 전에는 개시하지 않음" 추가 |

남은 것: `../prototype/data/golden/cases.json`은 `04` SOF 표를 복사해 둔 것이라 *(계산)* 표시가 없는 옛 문구 그대로다(계산 결과는 같다). prototype은 다른 세션이 작업 중이라 고치지 않았다.

## 10. `../prototype/engine/clock.py`와의 관계

- 같은 날 만든 체선료 데스크 데모(`../prototype/`)에 CLOCK이 이미 있다. SOF 텍스트 파서(`intake.py`)를 거쳐 계산하고, unittest로 TC-01~05를 통과하며, 화면·MCP와 연결돼 있다.
- 이 폴더는 브리프의 입력 형식(06 표준 이벤트), pytest, 독립 패키지 요구 때문에 따로 만들었다. 데모 코드는 고치지 않았다.
- 교차 검증(같은 TC, 두 구현): 기본 계산 6건과 문서 대안 3건(177,500 · 7,291.67 · 3,791.67), TC-01b 야간 대안 0이 모두 같다. 다른 값은 **TC-03 야간 대기 대안 하나**다(prototype 122,500 / clock 117,500). prototype이 앞 선박 이안 뒤 선석 전환 60분(`PLAN-TURNOVER` [가정])을 두기 때문이고, 둘 다 문서 정답은 아니다.
- [추천] 계산 코어를 하나로 합친다. 데모가 이 패키지를 코어로 쓰고 `intake.py`가 06 이벤트를 만들게 하는 방향이 자연스럽다. 결정은 팀 몫이다.

## 11. 한계와 다음 단계

- 항구 1개 · 계약 레이어 1개(CP) 계산서. 가역 레이타임, 선적항, SHEX 같은 시간 제외 규칙은 지원하지 않는다.
- 재투묘, 선석 간 이동(cl.9 지시 이동 산입), 재접안은 지원하지 않는다. 입력에 있으면 `CaseError`로 멈춘다.
- 레이캔(ASB-05-LAYCAN), 검역(free pratique), 항만당국 야간 하역 금지(ASB-07-NIGHT-PROHIBIT-*), 밸러스트 배출(ASB-07-BALLAST-EXCL)은 미구현이다.
- 다음 [추천]: (1) 멘토 인터뷰 뒤 [가정] 값과 룰 `status`를 교체한다. (2) 실제 SOF 양식으로 케이스를 20~50건으로 늘리고 분쟁 패턴을 넣는다(`06` §12). (3) INTAKE(LLM 추출)가 06 이벤트를 만들고 이 엔진이 검증·계산하는 경계를 고정한다. (4) §7-6을 위해 CP·SALES 계산서 2장 비교를 붙인다.

## 12. 디렉터리

```text
clock/
├─ README.md
├─ pyproject.toml          pytest 설정(pythonpath = ".")
├─ laytime/
│  ├─ __init__.py          공개 API: load_case, compute_statement, Policy, render_markdown …
│  ├─ __main__.py          CLI (python3 -m laytime)
│  ├─ model.py             입력 모델·검증 (06 SOF_EVENT·CONTRACT_TERMS + 확장)
│  ├─ engine.py            계산 엔진·쟁점·대안 계산·계산서 줄
│  ├─ rules.py             룰 레지스트리 (05 룰 ID·status)
│  ├─ render.py            Markdown 계산서·요약표
│  └─ fmt.py               표시 서식
├─ cases/                  TC-01, TC-01b, TC-02, TC-03, TC-04, TC-05, TC-05b (입력 + 문서 정답)
└─ tests/
   ├─ test_golden_tc.py    문서 정답 재현 (케이스 × 8개 검사)
   └─ test_engine.py       개시·이동·반액·펌핑·쟁점 §7-1~5·입력 검증·불변식·CLI
```
