# 데이터 계약 — 무엇을 넣으면 도는가

넣는 곳: `data/inbox/`에 파일을 두고 `make data` (또는 화면 「데이터 실행」에서 올리기, 또는 `POST /api/cases`).
같은 내용을 다시 넣으면 새로 만들지 않는다(키를 정렬한 JSON의 sha256 앞 16자리가 같으면 같은 데이터). 숫자 표기(`36`과 `36.0`)가 달라도 다른 데이터로 본다. CSV는 파일 이름이 id(`CSV-<이름>`)와 제목이 되므로 같은 행이라도 파일 이름이 다르면 새 데이터다.

## 형식 1 — CSV (입항 건만 있을 때)

엑셀에서 「CSV UTF-8」로 저장한 그대로 넣는다. 틀: [templates/arrivals.csv](templates/arrivals.csv) (예시 4척).

| 열 | 꼭 | 뜻 | 예 |
|---|---|---|---|
| `id` | ● | 입항 건 번호 | A |
| `vessel` | | 선명 | MR-DSL |
| `class` | ● | 선종 CR 원유 · PP 석유제품 · PC 화학 · LB 윤활유 · SP 특수 | PP |
| `biz` | ● | IM 수입 · EX 수출 · DI 내수 매입 · DO 내수 판매 | EX |
| `cargo_group` | ● | 제품 그룹 (부두가 받는 그룹이어야 배정된다) | DSL |
| `qty` | | 물량 | 300000 |
| `eta` | ● | 도착 예정 (KST, `2026-11-10T06:00` 또는 `2026-11-10 06:00`) | |
| `nor_tender` | | NOR 제출 시각. 없으면 ETA를 쓴다 | |
| `grt` `dwt` `loa` `pbl` `draft` | ● | 선박 제원 (부두 제원과 비교) | |
| `laycan_from` `laycan_to` | ● | LayCan | |
| `laytime_h` | ● | 허용 정박시간(시간) | 36 |
| `rate_usd_day` | ● | 하루 체선료(USD) | 26252 |
| `cfr` · `weather_half` | | true/false (y·n, yes·no, 1·0, o·x도 됨). 비우면 cfr=false, weather_half=true. `cfr`은 원유(CR)의 Laytime 배수에만 쓰이고, `weather_half`가 true면 기상 악화 시간의 ½을 공제한다(false면 공제 없음) | false |
| `rate_per_h` 또는 `work_hours` | ● 둘 중 하나 | 시간당 평균 하역량 또는 작업시간 | 11145 |
| `status` | | PLANNED(기본) · FIX · WORKING | FIX |
| `fix_berth` `fix_etb` | FIX·WORKING이면 ● | 고정된 부두·접안 시각 | #8 |
| `berths` | | 이 부두들 안에서만 (`#6;#7`) | |

계획 기간은 `PLAN_START`·`PLAN_END` 환경변수(화면에서는 'CSV 기간' 칸)로 준다. 둘 다 비우면 **가장 이른 ETA의 그날 0시부터 7일**, 끝만 비우면 시작 + 7일이다.
부두 제약(기상 악화·공사), 원유 탱크, 일출·일몰, 현행 계획은 CSV로 못 넣는다 → JSON을 쓴다.

## 형식 2 — JSON (요청 계약 그대로)

Python 엔진이 받는 모양 그대로다(원본 계약: `docs/milp/ppt/README.md` 6-2절). 예: [samples/example-3.json](samples/example-3.json) · [samples/sample-week-54.json](samples/sample-week-54.json).

```json
{
  "id": "MY-WEEK-47", "title": "11월 4주",
  "plan": {"start": "2026-11-16T00:00", "end": "2026-11-23T00:00"},
  "arrivals": [ { "id": "A", "class": "PP", "biz": "EX", "cargo_group": "DSL", "qty": 300000, "eta": "…",
                  "grt": 29597, "dwt": 45000, "loa": 183, "pbl": 85.5, "draft": 12.64,
                  "contract": {"laycan_from": "…", "laycan_to": "…", "laytime_h": 36, "rate_usd_day": 26252, "cfr": false},
                  "work": {"rate_per_h": 11145}, "status": "PLANNED" } ],
  "restrictions": [ {"id": "WX-1", "reason": "WEATHER", "berths": ["*"], "start": "…", "end": "…"} ],
  "inventory":    [ {"group": "CRUDE", "opening": 5500000, "min": 3000000, "max": 10000000, "flows": [{"from": "…", "to": "…", "use_per_h": 35000}]} ],
  "sun":          { "2026-11-16": ["07:03", "17:15"] },
  "current_plan": [ {"id": "A", "berth": "#6", "etb": "…"} ],
  "rule_patch":   { "demurrage.weather_basis": "USED" },
  "options":      { "generation": "auto", "grid_min": 30 }
}
```

`restrictions` 이후는 모두 선택이다. `sun`이 없으면 근사식으로 계산한다(운영에서는 공공데이터 출몰시각을 넣는다).

## 넣을 때 하는 검사 (Spring, 저장 전)

하나라도 틀리면 저장하지 않고 한 번에 돌려준다. 단, CSV 머리글이 틀리면(꼭 필요한 열이 없거나 모르는 열) 칸을 읽기 전에 머리글 오류만 먼저 돌려준다. 위치는 CSV 칸 오류면 `N행`(빈 줄을 뺀 뒤 머리글을 1행으로 센 번호라 엑셀 행 번호와 어긋날 수 있다), 검사 규칙 오류면 `arrivals[n] (id)`(n은 1부터 센 입항 건 순번, CSV에서는 n+1행)로 나온다. 예:

```text
✗ bad-arrivals.csv: 입력 검사 실패 5건
    - 3행 rate_usd_day가 숫자가 아님: 'abc'
    - arrivals[1] (X1).class는 [CR, PP, PC, LB, SP] 중 하나: 'ZZ'
    - arrivals[2] (X2).eta: 시간대가 붙은 값은 받지 않음 '2026-11-10T09:00+09:00' (KST 현지 시각 YYYY-MM-DDTHH:MM)
    - arrivals[2] (X2).contract.rate_usd_day가 없음
    - arrivals[2] (X2).work에 hours(작업시간) 또는 rate_per_h(시간당 평균 하역량)가 필요
```

- 입항 건: 필수 칸, 시각 형식(KST 현지 시각만, 시간대가 붙으면 거절), 선종·업무 구분 코드, `qty`(0 이상. JSON에서 `null`·빈 글자면 오류, CSV의 빈 칸은 '칸 없음'으로 본다), 부두 이름(규칙 표의 24개), FIX·WORKING의 부두·시각, 같은 id 두 번, LayCan 순서, laytime·요율 0 이상, 하역량(0보다 큼)·작업시간(0 이상), `cfr`·`weather_half`는 true/false
- 그 밖: 계획 시작 < 끝, 제약의 사유(WEATHER·WORK)·부두 배열·시작 < 끝, 탱크 min ≤ max, `sun` 형식, 현행 계획의 없는 id·부두·중복(FIX·WORKING 배는 fix와 같은 부두·ETB), `weather_basis`, `options`(generation은 auto·EXACT·GRID, grid_min 5~240 정수, max_wait_h 0~720 등)
- 경고(저장은 함): ETA가 계획 끝 뒤, **배정 가능한 부두가 없음**(제품 그룹·제원) → 그 데이터는 '후보 없음'이 된다, `qty`도 작업시간(`work.hours`)도 없음 → 물량 0으로 계산

## 정답이 있는 예시

| 파일 | 내용 | 정답 (Python 엔진 = Spring 재계산) |
|---|---|---|
| `samples/example-3.json` | #6·#7·#8 석유제품선 3척 + FIX 1척 + 기상 악화 6시간 | 기존 해석: 기준안 $25,641.62 → 1안 $7,192.30 · 팀 해석(팀 엔진 기본): 기준안 $9,252.07 = 1안 $9,252.07 |
| `samples/team-week-54.json` | 팀원 가상 데이터 54척 (팀원 `data/dummy` → `scripts/team-data-to-case.py`, 기상 예보·탱크 제외) | 팀 엔진 1안 $99,787.99 · 기존 엔진(팀 해석) $99,758.27 · 현행 계획 $258,059.24 |
| `samples/sample-week-54.json` | 멘토링 Sample data 주간 54건, 부두 24개, 원유 탱크 | 기존 해석: 기준안 $246,269.93 → 1안 $216,985.68, 현행 계획 위반 14건 · 팀 해석: S52·S54(수출선 Draft 14.16)가 갈 부두가 없어 후보 없음 |
| `templates/arrivals.csv` | 위 예시의 입항 건만 (기상 악화 없음) | 기준안 $28,248.31 → 1안 $9,252.07 |

## 결과가 남는 곳

- DB: `plan_case`(검사를 통과한 요청 JSON을 JSONB로 — 키 순서·공백은 바뀐다, CSV는 바꾼 JSON — 과 지문) · `run`(요약·재검증·솔버 응답 원본) · `run_step`(단계별 시간) · `decision_event`(사람의 선택, 추가 전용)
- 파일: `make data`가 `data/out/<데이터>-run<번호>.json`에 실행 요약 + 솔버 응답(산출 근거 trace 포함)을 쓴다
- 공공데이터 ETA: 매일 06:00 KST 수집 타이머(dmin-collector)가 `eta_snapshot`에 쌓는다. 처음 보는 입항, 신고 단계·ETA가 바뀐 입항이 새 줄이 된다. 수집할 때 입항마다 가장 나중 신고 하나만 넣으므로 두 수집 사이의 중간 신고는 남지 않는다
