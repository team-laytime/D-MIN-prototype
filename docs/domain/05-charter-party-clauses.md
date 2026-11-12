# 표준 용선계약 조항 맵과 룰 ID 초안

- 작성일: 2026-11-02
- 갱신: 2026-11-02 — CLOCK 프로토타입(`../../clock/`) 검증 결과 반영. ASB-07-HOURS와 서식 밖 룰 4개(§2-1) 등록, 룰 `status` 값을 prototype·clock과 통일(§6).
- 용도: 레이타임·체선료 계산 규칙이 "어느 계약 조항에서 나오는지"를 한 장으로 연결하고, 룰 엔진이 쓸 룰 ID를 미리 정한다. 조항 번호와 문구는 교재·기억 기반 요약이므로 **코딩 전에 반드시 서식 원문과 대조**한다 [확인 필요]. 원문 PDF는 저작권이 있어 저장소에 넣지 않고 링크·페이지 번호만 적는다.
- 표기: [사실] / [추론] / [확인 필요] / [쟁점]

---

## 1. 어떤 서식을 읽어야 하나

| 서식 | 발행 | 쓰임 | 우리 프로젝트에서의 역할 |
|---|---|---|---|
| **Asbatankvoy** | ASBA(미국 선박중개인협회), 1977 | 탱커 항해용선의 가장 널리 쓰이는 중립 서식. 메이저가 아닌 화주·트레이더 거래의 기본 | **룰셋의 기준 서식** [추천]. 공개 원문 접근 쉬움 |
| Shellvoy 6 | Shell, 2005 | 메이저 화주 서식. 서류·시효·펌핑 규정이 상세 | 시효·서류 요건 룰의 참고 |
| BPVOY4 (BPVOY5는 최신판 확인) | BP Shipping, 1998 | 메이저 화주 서식 | 펌핑 워런티·시효 룰의 참고 |
| ExxonMobil VOY2012 등 | 메이저 각사 | 참고 | 범위 밖 [확인 필요] |
| Asbagasvoy | ASBA | LPG 항해용선 | SK6 LPG 선박 룰 확장 시 참고 [확인 필요] |
| 메이저 GTC(BP·Shell 등 일반거래조건) | 각사 공개 | 원유·제품 매매계약의 레이타임·체선료 조항 | 매매계약 레이어(back-to-back) 룰의 참고 |

Asbatankvoy는 **Part I(박스: 선박·화물·레이캔·운임·레이타임 시간·체선료율 등 협상 변수)**과 **Part II(표준 조항)**로 되어 있고, 당사자가 **Rider(추가 조항)**를 덧붙인다. 룰 엔진 입력은 Part I 값 + Part II 규칙 + Rider 규칙 세 층이다.

---

## 2. Asbatankvoy Part II 조항 맵 (레이타임·체선료 관련) [확인 필요 — 원문 대조 전]

| 조항 | 요지 | 체선료 계산에 미치는 효과 | 룰 ID 초안 | 쟁점·메모 |
|---|---|---|---|---|
| cl.5 Laydays | 레이캔 시작일 전에는 레이타임이 개시되지 않음. 종료일까지 NOR 못 내면 용선주 해지권 | 개시 하한 | ASB-05-LAYCAN | 레이캔 전 조기 도착 선박의 대기는 선주 부담 |
| cl.6 Notice of Readiness | 관습 묘박지 도착 시 NOR(berth or no berth). 레이타임은 **NOR 수령 후 6시간** 또는 **접안 완료(sea terminal은 계류 완료, 부두는 all fast)** 중 **먼저 오는 때** 개시. NOR 후 용선주 통제 밖 사유로 접안이 지연되면 그 지연은 used laytime에 불산입 | 개시 규칙, 대기 예외 | ASB-06-NOR-START, ASB-06-BERTH-DELAY-EXC | [쟁점] 예외는 cl.9의 "reachable on arrival" 의무 때문에 범위가 좁음(The Laura Prima). "used laytime"만 언급하므로 체선 중엔 미적용 가능성 |
| cl.7 Hours for Loading and Discharging | Part I의 running hours를 레이타임으로 허용. 선박 상태·고장·설비 부족으로 인한 지연 불산입. **선주 또는 항만당국 규정의 야간 하역 금지**로 잃은 시간 불산입, **용선주·송하인·수하인의 야간 금지**는 산입. **묘박지→선석 이동, 밸러스트·슬롭 배출 시간 불산입** | 제외 규칙 | ASB-07-HOURS(Part I running hours = 허용 시간), ASB-07-VESSEL-FAULT, ASB-07-NIGHT-PROHIBIT-PORT(불산입), ASB-07-NIGHT-PROHIBIT-CHTR(산입), ASB-07-SHIFTING-EXCL, ASB-07-BALLAST-EXCL | [쟁점] SK 터미널의 주간 접안 제한은 "하역"이 아니라 "접안" 제한이며, 터미널(수하인 측) 규정인지 항만당국 규정인지에 따라 부담이 갈림 → 현업 확인 |
| cl.8 Demurrage | 허용 레이타임 초과 시간에 대해 **시간당, 비례**로 Part I 요율 지급. 화재·폭발·폭풍·파업·직장폐쇄·노동 제한, 또는 용선주·공급자·송하인·수하인 플랜트의 기계·설비 고장으로 발생한 체선은 **반액**. 선박 선원·예선·도선사 파업으로 인한 지연은 체선료 없음 | 요율·반액·면책 | ASB-08-RATE-PRORATA, ASB-08-HALF-RATE, ASB-08-CREW-STRIKE-EXC | [쟁점] 반액은 "그 사유로 발생한 체선"에 적용. 사유가 레이타임 중 발생했을 때의 적용 범위는 해석 갈림 |
| cl.9 Safe Berthing – Shifting | 용선주는 **도착 시 접근 가능한(reachable on her arrival)** 안전한 장소·부두를 지정·확보. 용선주는 선석 간 이동을 지시할 수 있고 비용은 용선주 부담, 그 시간은 used laytime에 산입 | 대기 위험 배분, 지시 이동 산입 | ASB-09-REACHABLE, ASB-09-CHTR-SHIFT-COUNT | 혼잡·야간 제한·기상으로 선석에 못 가면 용선주 책임이라는 판례 흐름(The Laura Prima, The Fjordaas, The Sea Queen) |
| cl.10 Pumping In and Out | 선적 펌핑은 용선주 비용·위험, 양하 펌핑은 선박 비용. 용선주 요구로 육상 배관을 물로 치환하는 시간은 used laytime에 산입 | 라인 치환 산입 | ASB-10-LINE-CLEAR-COUNT | **24시간/100 psi 펌핑 워런티는 표준 본문에 없고 Rider로 붙는 것이 보통** [확인 필요] → RIDER-PUMPING |
| cl.11 Hoses; Mooring at Sea Terminals | 호스는 용선주가 제공·연결·분리(선주 선택 시 선주가 용선주 위험·비용으로). **레이타임은 호스가 분리될 때까지 계속** | 종료 규칙 | ASB-11-END-HOSES | SBM(sea terminal)에서는 선박이 해저 호스 취급 장비를 갖출 의무 |
| cl.17 Quarantine | 용선주가 검역이 있는 항구로 보냈을 때의 지연은 used laytime에 산입. 단 지시 당시 용선주가 몰랐던 검역은 예외 | 검역 지연 배분 | ASB-17-QUARANTINE | 조항 번호 [확인 필요] |

### 2-1. 서식 조항 밖의 룰 — 판례 원칙(LAW-)과 엔진 기준(ENG-)

서식 조항이 아니라 판례나 엔진 기준에서 나오는 룰이다. `prototype/data/rules.json`과 `clock/laytime/rules.py`가 이미 이 ID를 쓴다.

| 룰 ID | 내용 | 근거 | 상태 |
|---|---|---|---|
| LAW-NOR-ARRIVAL | 도착(관습 묘박지 투묘) 전에 낸 NOR은 무효. 재제출 전까지 레이타임이 개시되지 않음 | The Mexico I, The Johanna Oldendorff (`07` §2) | [확인 필요] |
| LAW-NOR-WAIVER | 무효 NOR 후 용선주가 이의 없이 하역을 시작하면 하역 개시 시점부터 레이타임 | The Happy Day (`07` §2) | [확인 필요] |
| LAW-ONCE-ON-DEM | 일단 체선이면 계속 체선. "demurrage"를 명시하지 않은 레이타임 예외는 체선 중 미적용 | The Spalmatori, The Nikmary (`07` §2) | [쟁점] — 적용 결과는 §7-1처럼 플래그 |
| ENG-LOW-MARGIN | 체선이 없어도 레이타임 여유가 기준 미만이면 경고 | `04` 예제 1 교훈 | [가정] 기준 2시간 |

---

## 3. Shellvoy 6 · BPVOY4에서 달라지는 지점 [확인 필요 — 전부 원문 대조 필요]

| 주제 | Asbatankvoy | Shellvoy 6 / BPVOY4 (요약) | 룰 ID 초안 |
|---|---|---|---|
| 펌핑 워런티 | 본문 없음(Rider) | 본문에 포함. 전량 24시간 내 양하 또는 매니폴드 100 psi 유지. 미달 시 초과 시간은 선주 부담으로 공제. 육상 제한이 있었다면 선주는 터미널 확인서(LOP)로 면책 주장 | SV6-PUMPING, BPV4-PUMPING |
| 청구 시효(time bar) | 본문 없음(Rider) | Shellvoy 6: 양하 완료 후 **60일 내 체선 발생 통지, 90일 내 완전한 서류로 청구**, 미이행 시 청구권 소멸. BPVOY4: **90일 내 서류 완비 청구**, 미이행 시 소멸(The Abqaiq: 서류의 "실질적 충족" 기준) | SV6-TIMEBAR-60-90, BPV4-TIMEBAR-90 |
| 필수 서류 | 명시 없음 | NOR, SOF(선장·대리점·터미널 서명), 타임시트, 펌핑 로그, 항의서 등 목록 명시 | SV6-DOCS, BPV4-DOCS |
| 서류 대기 | 명시 없음 | 호스 분리 후 서류 대기가 일정 시간(예: 3시간)을 넘으면 초과분 산입하는 구조로 알려짐 | SV6-DOCS-WAIT, BPV4-DOCS-WAIT |
| 기상 반액 | 폭풍은 cl.8 반액 | 악천후·해상 상태로 인한 지연에 반액 규정이 별도로 있는 것으로 알려짐 | SV6-WEATHER-HALF, BPV4-WEATHER-HALF |
| 검역(free pratique) | WIFPON 관용구로 처리 | NOR 후 6시간 내 검역 허가를 못 받으면 NOR 무효로 보는 구조(The Eagle Valencia, Shellvoy 5) | SV-PRATIQUE-6H |

---

## 4. 매매계약(GTC) 레이타임 조항의 전형적 패턴 [추론 — 공개 GTC 구조 기반, 수치는 예시]

| 패턴 | 내용 | 룰 ID 초안 | 메모 |
|---|---|---|---|
| 항구별 허용 레이타임 | 예: 전량 화물 36시간, 부분 화물은 비례 | SALES-LAYTIME-ALLOW | 용선계약의 총 72시간과 다를 수 있음 → 계산서 2종 |
| NOR·통지시간 | 관습 묘박지 NOR, 6시간 또는 접안 중 빠른 때 | SALES-NOR-START | 용선계약과 유사 |
| 체선료율 상한 | 매매계약 체선료 = 실제 용선계약 요율, 상한 또는 시장 지표 연동 | SALES-RATE-CAP | 용선계약이 없을 때(자가 선박) 시장 지표 기준 |
| 시효·서류 | 예: 양하 후 60~90일 내 서류 완비 청구 | SALES-TIMEBAR | 용선계약 시효보다 짧으면 "갭" |
| 지급 조건 | 매수인·매도인이 실제로 선주에게 지급한 범위 내 등 | SALES-PAY-WHEN-PAID | 분쟁 요소 |
| 상대방 귀책 | 상대방 터미널·서류 지연은 상대방 부담 | SALES-COUNTERPARTY-FAULT | 터미널 기록이 증빙 |

---

## 5. 터미널 운영 룰 (SEAGATE 공개 자료 기반) → 룰 ID

| 룰 ID | 내용 | 출처 | 상태 |
|---|---|---|---|
| ULS-SBM-NIGHT | SK Buoy(SBM) 야간 계류 불가, 이안은 주야 가능 | Entry Guide 울산 | 공개자료 [사실] |
| ULS-SK38-DAYTIME | SK3~8: 공선 30,000GT 이상·적재 25,000GT 이상 선박은 접안 주간만, 이안 24시간 | Entry Guide 울산 | 공개자료 [사실] |
| ULS-SK12-DAYTIME | SK1~2: 아스팔트·윤활유·유황 선적선 외 주간 접·이안 | Entry Guide 울산 | 공개자료 [사실] |
| ULS-DAYTIME-DEF | "주간"의 정의 | 없음 | [가정] 07:00~17:30 → 현업 확인 |
| ULS-PILOT-MANDATORY | 접·이안·투묘·양묘 시 강제 도선(E-1~E-3 묘박지 제외), 항계 도착 2시간 전 호출 | Entry Guide 울산 | 공개자료 [사실] |
| ULS-DWT-MAX | 선석별 최대 DWT | 울산항만공사 표 | 기준일 미표기 → 최신값 확인 |
| ULS-DRAFT-UKC | 흘수 + 여유수심 ≤ 수심 | 없음 | [가정] UKC 값 현업 확인 |
| ULS-WEATHER-LIMIT | 풍속·파고 한계 초과 시 접안·하역 중단 | 안전규정에 수치 없음 | [확인 필요] |
| INC-NIGHT-2204 | 인천 접안 야간 제한 22:00~04:00 | Entry Guide 인천 | 공개자료 [사실] |

---

## 6. 룰 데이터 스키마 (룰 엔진 입력) [추천]

```yaml
rule_id: ASB-07-SHIFTING-EXCL
title: 묘박지→선석 이동 시간은 used laytime에 불산입
source:
  form: Asbatankvoy
  part: II
  clause: 7
  text_ref: "Time consumed by the vessel in moving from loading or discharge port anchorage to her loading or discharge berth ... will not count as used laytime"   # 원문 대조 후 확정
  url: null                      # 공개 PDF 링크, 저장소에는 원문 미포함
scope:
  stage: discharge               # load | discharge | both
  applies_during: laytime        # laytime | demurrage | both
  terminal: any
condition:
  event_from: ANCHOR_AWEIGH
  event_to: ALL_FAST
effect:
  counts: no                     # yes | no | half
status: verify                   # confirmed | public | verify | assumed | disputed (아래 설명)
disputes:
  - "체선 중 발생한 이동에도 적용되는지 (once on demurrage) → 자동 판정 금지, 플래그"
verified_by: null
verified_on: null
```

판정 결과에는 항상 `rule_id`, 적용된 SOF 행, 계산식이 함께 붙는다(핸드오프 원칙).

`status` 값: `confirmed`(현업·원문 확인 완료, `verified_by`·`verified_on` 기록) · `public`(공개자료로 확인 [사실]) · `verify`(서식 원문·판례 대조 전 [확인 필요]) · `assumed`(임의로 둔 값 [가정]) · `disputed`(해석이 갈림 [쟁점]). `prototype/data/rules.json`과 `clock/laytime/rules.py`도 같은 값을 쓴다(2026-11-02 현재 `confirmed`는 없음).

---

## 7. 룰 엔진이 자동 판정하지 말고 플래그만 해야 할 쟁점

1. 체선 중 이동(shifting) 시간의 산입 여부 (ASB-07 vs once on demurrage)
2. 야간 접안 제한·기상으로 인한 대기의 부담 주체 (ASB-06-BERTH-DELAY-EXC vs ASB-09-REACHABLE)
3. 레이타임 중 발생한 폭풍 중단에 대한 반액 적용 범위 (ASB-08-HALF-RATE)
4. 대리점의 NOR 수령 서명이 하자 포기(waiver)인지
5. 서류 대기 시간 산입(서식별 상이)
6. 매매계약과 용선계약 레이타임·시효 불일치로 인한 갭

위 6개는 시뮬레이터와 CLAIM 모듈 모두에서 "쟁점" 배지로 표시하고 두 가지 계산을 함께 보여준다 [추천].
