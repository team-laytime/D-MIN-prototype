# 모의 클레임 케이스 — M/T ULSAN GLORY 체선료 청구 패킷

- 작성일: 2026-11-02
- 용도: M1~M5를 한 번에 묶는 종합 실습. 수강생은 "SK 체선료 데스크 담당자"가 되어 선주 청구서를 검토하고 회신 논지를 쓴다. 모든 문서·수치·선박명은 **가상**이다.
- 소요: 90분(개인 40분 + 조별 토론 30분 + 해설 20분)
- 통과 기준(`00-syllabus.md` §4): 재계산 금액이 모범답안과 일치, 쟁점 3개 이상 식별, 회신이 조항·SOF 행을 인용.

---

## 패킷 1 — Fixture recap (발췌)

```
M/T ULSAN GLORY (가상) — VLCC 310,000 DWT
OWNERS: NORTHSTAR TANKERS (가상)     CHARTERERS: SK ENERGY (FOB 매입, 자가 용선)
CARGO 270,000 MT CRUDE  LOAD 1SP RAS TANURA  DISCH 1SP ULSAN (SBM)
LAYTIME 72 HRS SHINC TOTAL REVERSIBLE
DEMURRAGE USD 120,000 PDPR
NOR ATDNSHINC, 6 HRS NOTICE, WIBON
PUMPING WARRANTY: FULL CARGO WITHIN 24 HRS OR MAINTAIN 100 PSI AT SHIP'S RAIL, PROVIDED SHORE FACILITIES PERMIT
TIME BAR 90 DAYS FROM COMPLETION OF DISCHARGE, FULLY DOCUMENTED (NOR, SOF, TIMESHEET, PUMPING LOG, LOP)
CP ASBATANKVOY + RIDER. ENGLISH LAW, LONDON ARBITRATION (LMAA)
```

## 패킷 2 — 선주 측 선적항 요약 (Ras Tanura)
선주 계산서 첨부 요약: 선적항 레이타임 사용 **36h 00m**(개시 ~ 호스 분리, 이동 2h 제외 후). 선적항 SOF 원본은 미첨부.

## 패킷 3 — 선주 제출 SOF (울산, 선장·대리점 서명, 터미널 서명 없음)

| 시각(KST) | 사건 |
|---|---|
| D1 09:40 | 울산 E-2 묘박지 투묘 |
| D1 10:00 | NOR 제출·대리점 수령 |
| D2 19:00 | 앞 선박(VLCC) SBM 이안 |
| D3 07:00 | 양묘, SBM 이동 개시 |
| D3 09:00 | 계류 완료(finished mooring) |
| D3 10:00 | 호스 연결 |
| D3 10:30 | 양하 개시 |
| D3 15:00 | 선장 LOP 발행: 육상 배압 높아 양하율 제한 |
| D3 22:00 | 강풍으로 터미널 지시 양하 중단 |
| D4 04:00 | 양하 재개 |
| D4 19:30 | 양하 완료 |
| D4 20:30 | 호스 분리 |
| D4 22:00 | 서류 선적 완료(documents on board) |
| D4 23:30 | 이안 |

## 패킷 4 — 선주 레이타임 계산서와 청구서

| 항목 | 선주 계산 |
|---|---|
| 개시 | D1 16:00 (NOR + 6h) |
| 종료 | D4 22:00 (documents on board) |
| 경과 | 78h 00m |
| 공제 | 없음 ("vessel on demurrage from D3 04:00; no exceptions apply") |
| 사용 | 78h 00m |
| 허용 | 36h 00m (72 − 선적항 36) |
| 체선 | 42h 00m |
| 금액 | 42 × 120,000 / 24 = **USD 210,000** + 지연이자 연 8% 청구 |
| 청구 도착 | 양하 완료 후 **75일째** |
| 첨부 | NOR 사본, SOF(2자 서명), 계산서, 펌핑 로그, LOP, 인보이스 |

## 패킷 5 — SK 터미널 기록

| 기록 | 내용 |
|---|---|
| AIS·PTMS | D1 09:35 항계 진입, 09:40 투묘(묘박지 내) |
| 선석 로그 | 앞 VLCC D2 19:00 이안. SBM 야간 계류 불가 규정으로 익일 주간 계류 지시 |
| 계류 작업 | D3 07:00~09:00 |
| 호스 | 연결 D3 10:00, 분리 D4 20:30 (터미널 기록 일치) |
| 중단 | D3 22:00 터미널 지시 중단(풍속 18 m/s, 터미널 한계 초과 [가정]), D4 04:00 재개 |
| 기상 관측(KMA·터미널) | D3 21:40 ~ D4 03:50 평균 풍속 16~19 m/s |
| 배압·수용 | D3 12:00~15:30 육상 배압 상승(탱크 전환 작업). 그 외 제한 없음 |
| 펌핑 로그(선박) | 매니폴드 압력 평균 102 psi, 배압 상승 구간 외 100 psi 이상 유지. 실양하 시간 27h(중단 6h 제외) |
| 서류 | 대리점 사유로 B/L 등 전달 1h 30m 지연 |

---

## 과제

1. **시효**: 청구는 시효 내인가? 서류는 "fully documented"인가? 무엇을 요구할 것인가?
2. **NOR**: 유효한가? 근거는?
3. **개시·종료**: 선주의 개시·종료 시각에 동의하는가? Asbatankvoy에서 종료는 무엇인가?
4. **체선 전환과 이동**: 체선 개시 시각은? D3 07:00~09:00 이동은 산입인가 공제인가?
5. **반액**: 적용 구간과 근거는?
6. **펌핑 워런티**: 공제 가능한가? LOP의 의미는?
7. **재계산**: 계산서를 완성하고 선주 청구와의 차이를 사유 코드로 분해하라.
8. **이자**: 청구된 지연이자를 어떻게 다룰 것인가?
9. **회신**: 영문 회신 골격과 국문 내부 메모를 쓰라.
10. **전가·교훈**: 이 건은 매매계약으로 전가할 수 있는가? 운영상 교훈은?

---

## 모범답안

### 1. 시효·서류
- 양하 완료 D4 19:30 기준 90일 시효, 청구는 75일째 → **시효 내**.
- 첨부 서류는 recap 목록(NOR, SOF, 타임시트, 펌핑 로그, LOP)을 충족한다. 터미널 서명 없는 SOF는 선주 측 문서로서는 무효 사유가 아니다. 다만 **선적항 SOF 원본**이 없어 가역 레이타임의 선적항 사용 36h를 검증할 수 없다 → 보완 요청(without prejudice), 그 전까지 36h를 잠정 채택하고 `LOAD_PORT_UNKNOWN` 플래그.

### 2. NOR
- 투묘 D1 09:40(AIS·PTMS 일치) 후 10:00 제출·수령, 관습 묘박지, WIBON → **유효**. 레이캔 내 가정.

### 3. 개시·종료
- 개시: 선석 점유 중이므로 NOR + 6h = **D1 16:00**. 선주와 일치.
- 종료: Asbatankvoy cl.11 "레이타임은 호스 분리까지" → **D4 20:30**. 선주는 서류 완료 D4 22:00을 썼으나 Asbatankvoy 본문·recap에 서류 대기 산입 조항이 없다 → **1h 30m 불인정**(`DOCS_WAIT`).

### 4. 체선 전환·이동
- 산입 누계가 36h에 도달하는 시각 = D1 16:00 + 36h = **D3 04:00**(묘박지 대기 중 체선 돌입).
- 이동 D3 07:00~09:00은 체선 개시 후 → once on demurrage 원칙상 **산입**이 통설. 용선주로서 공제를 주장할 여지는 있으나 성공 가능성은 낮음 → `SHIFT_ON_DEM` 쟁점으로 기록하고 **협상 카드**로만 사용.

### 5. 반액
- D3 22:00~D4 04:00 터미널 지시 중단, 풍속 16~19 m/s 관측 → cl.8 "storm"으로 주장 가능. 체선 중·접안 중 발생 → **6h 반액**(`HALF_RATE_MISSING`). 증빙: 터미널 중단 지시 기록 + KMA 관측. "storm"의 정의가 다툼 소지이므로 기상 자료를 첨부.

### 6. 펌핑 워런티
- 보증은 "24시간 내 **또는** 100 psi 유지". 실양하 27h > 24h이지만 매니폴드 압력이 배압 상승 구간 외 100 psi 이상 유지 → **보증 충족**, 공제 불가. 배압 상승 구간(D3 12:00~15:30)은 육상 사유이며 선장 LOP가 이를 기록 → 이 구간을 선주 귀책으로 돌릴 수 없다. `PUMPING_SHORE` 플래그는 "공제 없음"으로 종결.

### 7. 재계산

| 항목 | 값 | 근거 |
|---|---|---|
| 개시 | D1 16:00 | ASB-06-NOR-START |
| 종료 | D4 20:30 | ASB-11-END-HOSES |
| 경과 | 76h 30m | |
| 공제 | 0 (이동은 체선 중 → 산입) | once on demurrage, SHIFT_ON_DEM 플래그 |
| 사용 | 76h 30m | |
| 허용 | 36h (선적항 36h 잠정) | LOAD_PORT_UNKNOWN |
| 체선 | **40h 30m** | 체선 개시 D3 04:00 |
| 반액 구간 | 6h (D3 22:00~D4 04:00) | ASB-08-HALF-RATE |
| 전액 구간 | 34h 30m | |
| 금액 | 34.5 × 5,000 + 6 × 2,500 = 172,500 + 15,000 = **USD 187,500** | |
| 대안(이동 공제 시) | 32.5 × 5,000 + 15,000 = USD 177,500 | 협상 카드 |

**차이 분해**: 선주 210,000 − 재계산 187,500 = **USD 22,500** = 서류 대기 1.5h × 5,000 = 7,500 (`DOCS_WAIT`) + 반액 6h × 2,500 = 15,000 (`HALF_RATE_MISSING`).

### 8. 이자
- recap에 이자 조항 없음 → 계약상 근거 없음으로 **거절**. 중재 판정 시 재량 이자는 별개. 합의 시 협상 항목.

### 9. 회신

**영문 골격(without prejudice)**
> We refer to your demurrage claim dated __ for M/T ULSAN GLORY at Ulsan (USD 210,000). We accept that laytime commenced at D1 16:00 and that the vessel was on demurrage from D3 04:00. However: (a) under Clause 11 laytime and time on demurrage ceased upon disconnection of hoses at D4 20:30; the period to D4 22:00 awaiting documents is not for Charterers' account; (b) discharge was suspended by the terminal from D3 22:00 to D4 04:00 owing to storm conditions (wind 16–19 m/s, records attached), for which demurrage is payable at half rate under Clause 8; (c) no contractual basis exists for the interest claimed. Our recalculation: 40.5 hours on demurrage, of which 6 hours at half rate, totalling USD 187,500. Please also provide the load port SOF to verify laytime used at Ras Tanura. All rights reserved.

**국문 내부 메모**
> 시효 내(75/90일), 서류 충족(선적항 SOF 보완 요청). NOR 유효. 개시 D1 16:00 동의, 종료는 호스 분리 D4 20:30(서류 1.5h 불인정). 체선 40h 30m 중 강풍 6h 반액. 펌핑 공제 없음(압력 유지). 재계산 USD 187,500(청구 대비 −22,500). 쟁점: 체선 중 이동 2h(공제 시 −10,000, 성공 가능성 낮음) → 협상 카드. 이자 거절. 권고: 187,500 제시, 177,500~187,500 사이 합의 재량 요청.

### 10. 전가·교훈
- SK가 FOB 매입·자가 용선이므로 선주에게 직접 지급. 매매계약(매도인)으로 전가할 대상 아님(울산 양하 지연은 SK 측 사유). → **갭 없음, 전액 자사 비용**.
- 운영 교훈: 체선 40.5h 중 **대기가 39h**(D1 16:00~D3 07:00)였고 원인은 앞 선박 점유 + SBM 야간 계류 금지. D1 16:00 시점에 "D3 04:00 체선 돌입, 노출 약 USD 190,000" 경고가 있었다면 앞 선박 하역 속도·탱크 여유 조정 여부를 검토할 수 있었다(EXPLAIN 모듈의 가치). 터미널의 기상·중단 기록이 USD 15,000을, cl.11 지식이 USD 7,500을 지켰다(CLAIM 모듈의 가치).

---

## 채점 루브릭

| 항목 | 배점 | 기준 |
|---|---|---|
| 시효·서류 판단 | 10 | 시효 내 판정 + 선적항 SOF 보완 요청 |
| NOR 판정 | 10 | 유효, AIS·묘박지 근거 |
| 종료 시점 | 15 | 호스 분리 적용, 서류 1.5h 불인정 |
| 체선 전환·이동 | 15 | D3 04:00, once on demurrage 설명, 쟁점 표시 |
| 반액 | 15 | 6h, 증빙 지정 |
| 펌핑 | 10 | "또는" 조건 이해, 공제 없음 |
| 금액·차이 분해 | 15 | 187,500 / 22,500 = 7,500 + 15,000 |
| 회신 품질 | 10 | 조항·SOF 행 인용, 간결, without prejudice |
| 합계 | 100 | 70점 이상 통과 |
