# M2 · 용선계약과 매매계약의 구조

- 핵심 질문: 시간의 값은 어느 문서, 어느 조항에서 정해지나?
- 선수 자료: `../05-charter-party-clauses.md`
- 표기: [사실] / [추론] / [확인 필요] / [쟁점]

## 학습 목표
1. 용선의 네 형태와 체선료가 존재하는 자리를 구분한다.
2. 항해용선 계약의 물리적 구조(recap → Part I → Part II → Rider)와 해석 우선순위를 설명한다.
3. Asbatankvoy의 레이타임·체선료 관련 조항을 찾아 요약하고, 메이저 서식과의 차이를 말한다.
4. 매매계약(GTC)의 레이타임 조항과 Incoterms가 체선료 흐름을 어떻게 결정하는지 설명한다.
5. 가상 recap을 읽고 룰 엔진 입력값으로 바꾼다.

---

## 1. 용선의 네 형태와 체선료의 자리

| 형태 | 내용 | 선주가 받는 돈 | 항구 지연 위험 | 체선료 |
|---|---|---|---|---|
| 항해용선 Voyage charter | 화물 1건을 A→B 운송 | 운임 freight | 레이타임으로 배분 | **있음** |
| 운송계약 COA (Contract of Affreightment) | 일정 기간 여러 항차 운송 약속 | 항차별 운임 | 항차별 레이타임 | **있음**(항차마다) |
| 정기용선 Time charter | 기간 단위로 배를 빌림. 운항 지시는 용선주 | 용선료 hire(일당) | 용선주가 용선료로 그대로 부담 | 없음(개념상 불필요) |
| 나용선 Bareboat | 선원 없이 배만 빌림 | 용선료 | 용선주 | 없음 |

정유사는 원유 도입에 COA·spot 항해용선을 섞어 쓰고, 일부는 정기용선 선대를 운영할 수 있다 [추론]. **체선료 Agent의 대상은 항해용선(spot·COA)과 매매계약의 레이타임 조항**이다.

---

## 2. 항해용선 계약의 물리적 구조

```
① Fixture recap (브로커 메일·메신저) — 합의된 주요 조건 요약. "fixed"의 증거
② Part I (박스 서식) — 선박·화물·레이캔·운임·레이타임 시간·체선료율·중재지 등 변수
③ Part II (인쇄 조항) — 표준서식 본문(Asbatankvoy 26개 조항 등)
④ Rider / Additional clauses — 당사자 맞춤 추가 조항(펌핑 워런티, 시효, 서류, 제재, 전쟁 등)
⑤ Side letters, 이후 수정(addenda)
```

**해석 우선순위** [사실, 영국법 일반 원칙]: 당사자가 특별히 협상해 넣은 문구(타자·수기·Rider)가 인쇄된 표준 문구(Part II)보다 우선한다. 충돌이 있으면 "특별 > 일반". 그래서 룰 엔진은 Part II 기본 룰 위에 Rider 룰을 **덮어쓰기**하는 구조여야 한다(`05` §6 스키마의 `source.part`).

실무 포인트: recap만 있고 정식 서명본이 없는 거래도 많다. recap의 약어가 곧 계약이다(§8 실습).

---

## 3. Asbatankvoy 조항 지도 [확인 필요 — 조항 번호·제목은 원문 대조 전]

| 묶음 | 조항(번호는 원문 대조 필요) | 레이타임·체선료와의 관계 |
|---|---|---|
| 선박·화물 보증 | 1 Warranty–Voyage–Cargo, 13 Cargoes excluded(증기압·인화점), 16 General cargo | 준비 완료(readiness)의 전제 |
| 운임 | 2 Freight, 3 Deadfreight, 12 Dues–Taxes–Wharfage | 체선료와 별개 |
| 항구 지정 | 4 Naming loading and discharge ports, 15 Two or more ports counting as one | 복수 선석·항구 간 이동 시간 처리 |
| **시간 핵심** | **5 Laydays, 6 Notice of Readiness, 7 Hours for loading and discharging, 8 Demurrage, 9 Safe berthing–Shifting, 10 Pumping in and out, 11 Hoses; Mooring at sea terminals, 17 Quarantine** | M3의 전부 |
| 예외·책임 | 14 Ice, 18 Cleaning, 19 General exceptions, 23 Breach | 지연의 귀책 판단 보조 |
| 서류·법 | 20 Bills of lading, 21 Lien, 22 Agents, 24 Arbitration(뉴욕 또는 런던, Part I 선택), 25 Sublet, 26 Oil pollution | 분쟁 절차 |

### 3-1. 시간 핵심 조항의 요지 (M3에서 규칙으로 다시 다룸)

| 조항 | 요지 [확인 필요] | 룰 ID |
|---|---|---|
| 5 Laydays | 레이캔 시작 전 레이타임 미개시(용선주 동의 제외). 종료일까지 NOR 못 내면 해지권 | ASB-05-LAYCAN |
| 6 NOR | 관습 묘박지 도착 시 NOR(berth or no berth). 6시간 후 또는 접안 완료 중 빠른 때 개시. 용선주 통제 밖 사유의 접안 지연은 used laytime 불산입 | ASB-06-NOR-START, ASB-06-BERTH-DELAY-EXC |
| 7 Hours | Part I의 running hours 허용. 선박 귀책 불산입. 선주·항만당국 야간 하역 금지 불산입, 용선주·송하인·수하인 금지는 산입. 묘박지→선석 이동, 밸러스트·슬롭 배출 불산입 | ASB-07-* |
| 8 Demurrage | 시간당 비례 지급. 화재·폭발·폭풍·파업·플랜트 고장은 반액. 선원·예선·도선 파업은 면책 | ASB-08-* |
| 9 Safe berthing–Shifting | reachable on arrival 선석 제공 의무. 용선주 지시 이동은 비용·시간 용선주 부담 | ASB-09-* |
| 10 Pumping | 선적 펌핑 용선주, 양하 펌핑 선박 비용. 라인 치환 요구 시 산입. **24h/100psi 보증은 본문에 없고 Rider** | ASB-10-LINE-CLEAR-COUNT, RIDER-PUMPING |
| 11 Hoses | 레이타임은 호스 분리까지 계속 | ASB-11-END-HOSES |
| 17 Quarantine | 검역 지연은 산입(용선주가 몰랐던 검역은 예외) | ASB-17-QUARANTINE |

---

## 4. 메이저 서식(Shellvoy 6, BPVOY4·5)은 무엇이 다른가 [확인 필요]

| 주제 | Asbatankvoy(중립 서식) | 메이저 서식(화주 작성) | 함의 |
|---|---|---|---|
| 작성 주체 | 중개인 협회 | Shell·BP 등 화주 | 화주에게 유리한 규정이 많음(상세한 공제·시효·서류 요건) |
| 레이타임·체선료 규정 | 간결(6~11조) | 매우 상세: 개시·중단·종료 사유 열거, 선박 귀책 공제 열거 | 룰 수가 2~3배 |
| 펌핑 워런티 | Rider | 본문 포함(24h/100psi, 육상 제한 시 LOP) | 공제 자동화의 근거 |
| 시효 | 없음(Rider) | 통지·서류 기한 명시(Shellvoy 6: 60일/90일, BPVOY4: 90일로 알려짐) | 카운트다운 룰 |
| 서류 | 없음 | 필수 서류 목록 | 체크리스트 룰 |
| 서류 대기 | 없음 | 호스 분리 후 일정 시간 초과분 산입 구조로 알려짐 | 종료 룰 변형 |
| 기상 반액 | cl.8 storm | 별도 악천후 반액 조항이 있는 것으로 알려짐 | 반액 룰 변형 |

결론: **룰셋은 "서식별 프로파일"로 설계**한다. 기본(Asbatankvoy) 프로파일 위에 서식·Rider 프로파일이 덮어쓴다.

---

## 5. Rider의 전형적 항목

| 항목 | 내용 | 룰 영향 |
|---|---|---|
| Pumping warranty | 24h 또는 100 psi 유지, 미달 시 초과 시간 선주 부담, 육상 제한 시 LOP로 면책 | RIDER-PUMPING |
| Time bar / Documentation | 청구 기한과 필수 서류 | RIDER-TIMEBAR, RIDER-DOCS |
| ETA notices | 72/48/24h 통지 의무, 미이행 시 개시 지연 | RIDER-ETA |
| NOR 방식 | 이메일 허용, 수신 확인 방식, ATDNSHINC | 개시 룰 입력 |
| Bunkering / Deballasting | 하역 중 병행 허용 여부, 지연 시 귀책 | 공제 룰 |
| Early departure procedure (EDP) | 서류 완비 전 출항 허용 절차(제품 트레이드) | 종료 룰 |
| Sanctions / War risks / Weather routing | 거래 적법성·항로 | 접안 가부 |
| Charterer's agents | 대리점 지정 | SOF 기록 주체 |

---

## 6. 매매계약(GTC)의 레이타임·체선료 조항 [추론 — 메이저사 공개 GTC 구조 기반, 수치는 예시]

원유·제품 매매계약은 보통 메이저·트레이더의 **일반거래조건(GTC)**을 끌어다 쓴다. 그 안에 "Laytime and Demurrage" 섹션이 있다.

| 항목 | 전형 패턴 | 메모 |
|---|---|---|
| 허용 레이타임 | 항구별, 예: 전량 화물 36시간 SHINC, 부분 화물 비례 | 용선계약 총 72시간과 다른 숫자 |
| NOR·개시 | 관습 묘박지 NOR, 6시간 후 또는 접안 중 빠른 때 | 용선계약과 유사 |
| 제외 | 이동 시간, 선박 귀책, (일부) 기상 | 서식별 |
| 체선료율 | 실제 용선계약 요율. 용선계약이 없으면 시장 지표(AFRA·Worldscale 기반) | "용선계약 요율을 넘지 않는다" 상한 구조가 흔함 |
| 시효 | 예: 양하 완료 후 60~90일 내 완전한 서류로 청구 | 용선계약 시효보다 짧으면 **갭** |
| 지급 조건 | "실제로 선주에게 지급한 범위 내"(pay-when-paid) 조항이 있을 수 있음 | 분쟁 요소 [확인 필요] |
| 상한 | 체선료 총액·기간 상한을 두기도 함 | 갭의 원인 |

**back-to-back 갭**: 용선계약에서 선주에게 100을 내고 매매계약으로 80만 돌려받으면 20은 내 손실이다. 갭은 (1) 허용 시간 차이, (2) 제외 규칙 차이, (3) 요율 상한, (4) 시효 차이, (5) 서류 요건 차이에서 생긴다. CLAIM 모듈은 두 계산서를 나란히 두고 갭을 표시한다.

---

## 7. Incoterms가 정하는 "누가 용선주인가"

| 조건 | 선박 수배(용선주) | 선적항 지연 | 양하항 지연 | SK가 매수인일 때 | SK가 매도인일 때 |
|---|---|---|---|---|---|
| FOB | 매수인 | 매도인 책임(매매계약 레이타임) | 매수인 책임 | SK가 용선주. 울산 양하 지연은 SK가 선주에게 직접 | SK 선적항(울산) 지연은 매수인이 SK에 청구 |
| CFR / CIF | 매도인 | 매도인 책임 | 매수인 책임(매매계약) | 매도인이 용선주. 울산 지연은 SK가 매도인에게 | SK가 용선주. 상대 항구 지연은 매수인에게 역청구 |
| DES / DAP | 매도인 | 매도인 | 매수인(인도 후) | 울산 지연분을 SK가 매도인에게 | — |

핵심: **울산 SK 선석의 지연은 어느 조건에서도 SK 비용이 되기 쉽다**(`../01` §3). 다른 점은 "누구에게, 어느 계약으로 내느냐"뿐이다.

---

## 8. 실습 — 가상 recap 읽기

```
M/T DONGHAE PIONEER (가상) — AFRAMAX 105,000 DWT
ACCT  SK ENERGY (CHARTERERS)                 OWNERS: XYZ TANKERS (가상)
CARGO 80,000 MT CRUDE OIL 5% MOLOO
LOAD  1SP RAS TANURA        DISCH 1SP ULSAN (SK8 OR SBM AT CHRTS OPTION)
LAYCAN 20-22 NOV 2026
FREIGHT WS 95 (가정)
LAYTIME 72 HRS SHINC TOTAL, REVERSIBLE
DEMURRAGE USD 55,000 PDPR
NOR ATDNSHINC, 6 HRS NOTICE
PUMPING WARRANTY 24 HRS / 100 PSI AT SHIP'S RAIL
TIME BAR 90 DAYS FROM COMPLETION OF DISCHARGE, FULLY DOCUMENTED
CP FORM ASBATANKVOY + CHRTS RIDER CLAUSES 1-25
LAW/ARB ENGLISH LAW, LONDON ARBITRATION LMAA
```

| 약어 | 뜻 | 룰 엔진 필드 |
|---|---|---|
| ACCT | 용선주 계정 | PORT_CALL.charterer |
| MOLOO | More or less in owner's option(수량 가감 선주 선택) | 수량 |
| 1SP | 1 safe port | 항구 안전 보증 |
| LAYCAN | 레이캔 | CONTRACT_TERMS.laycan |
| WS 95 | Worldscale 95% | 운임(체선료 무관) |
| SHINC | Sundays/holidays included | running hours 확인 |
| TOTAL, REVERSIBLE | 선적+양하 합산 72h | laytime_total_hours=72, reversible=true |
| PDPR | per day pro rata | demurrage_rate_usd_day=55000, 비례 |
| ATDNSHINC | NOR을 주야·일·공휴일 무관 제출 가능 | NOR 방식 |
| 6 HRS NOTICE | 통지시간 | notice_hours=6 |
| PUMPING WARRANTY | 24h/100psi | pumping_warranty_hours=24, psi=100 |
| TIME BAR 90 DAYS FULLY DOCUMENTED | 시효·서류 | time_bar_docs_days=90, required_documents |
| LMAA | 런던해사중재인협회 | 분쟁 절차 |

연습: 위 recap에서 양하항 허용 레이타임은 몇 시간인가? → 총 72h 가역이므로 **선적항 사용분을 알아야** 양하항 잔여가 나온다. 선적항 SOF가 없으면 가정값을 쓰고 플래그한다(`../07` 함정 10).

---

## 9. 준거법과 분쟁 해결
- 탱커 항해용선은 영국법·런던 중재(LMAA)가 흔하고, Asbatankvoy는 Part I에서 뉴욕 또는 런던을 고른다 [사실]. 이 강의의 판례가 영국 판례인 이유다.
- 매매계약도 영국법이 많다. 국내 거래는 한국법·대한상사중재원이 될 수 있다 [추론].
- 실무에서 대부분의 체선료 분쟁은 중재 전 협상으로 끝난다. 그래서 "근거 있는 계산서와 회신"이 곧 무기다.

---

## 10. 자주 하는 오해
1. "표준서식이면 조건이 다 같다" → Part I 숫자와 Rider가 다르면 전혀 다른 계약이다.
2. "매매계약은 체선료와 무관하다" → 매매계약에 레이타임 조항이 있고, SK가 실제로 돈을 내는 경로일 수 있다.
3. "FOB면 SK는 체선료와 무관" → SK가 매수인이면 SK가 용선주가 되어 선주에게 직접 낸다.
4. "펌핑 워런티는 표준 조항" → Asbatankvoy 본문에는 없고 Rider다 [확인 필요].
5. "시효는 법이 정한다" → 계약이 정하는 실권 기한이 먼저다. 60~90일로 짧다.

## Agent에 주는 시사점
- 계약 파싱(INTAKE)은 recap 약어 사전을 가져야 한다. 룰셋은 서식 프로파일 + Rider 덮어쓰기 구조.
- 매매계약·용선계약 계산서를 분리하고 갭을 계산하는 것이 CLAIM의 차별점.

## 확인 문제
1. recap에 "LAYTIME 72 HRS SHINC TOTAL, REVERSIBLE"이 있고 선적항에서 40시간을 썼다. 양하항 허용은?
2. 용선주 Rider 조항과 Asbatankvoy Part II가 충돌하면 무엇이 우선하는가?
3. CIF로 원유를 산 SK는 울산 양하 지연 체선료를 누구에게 내는가?

**정답** 1. 32시간(72−40). 2. 특별히 협상한 Rider가 인쇄 조항보다 우선. 3. 매도인(매도인이 용선주로 선주에게 내고, 매매계약으로 SK에게 청구).
