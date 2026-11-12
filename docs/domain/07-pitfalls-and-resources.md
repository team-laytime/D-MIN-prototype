# 함정 목록, 판례, 학습 자료

- 작성일: 2026-11-02
- 용도: (1) Agent가 자동 판정하지 말고 걸러내야 할 함정을 미리 적는다. (2) 팀원이 더 깊이 공부할 때 어디서 무엇을 읽을지 안내한다.
- 판례의 사건명·연도·법원은 교재 기억 기반이므로 **학습 시 교재·판례집으로 대조**한다 [확인 필요]. 법률 자문이 아니라 도메인 학습 자료다.

---

## 1. Agent가 걸러야 할 함정 16개

| # | 함정 | 왜 생기나 | 판정 방향(통설) | Agent 체크 방법 | 모듈 |
|---|---|---|---|---|---|
| 1 | 도착 전 조기 NOR | 선장이 레이타임을 빨리 돌리려고 항해 중 송신 | 무효. 재제출 전까지 개시 안 됨(The Mexico I) | NOR 시각 vs ANCHORED·AIS 묘박지 진입 시각 | CLAIM |
| 2 | 준비 미완 상태의 NOR | 검역·탱크 세정·서류 미완 | 무효 가능(The Tres Flores 류) | FREE_PRATIQUE 시각, 탱크 검사 결과 대조 | CLAIM |
| 3 | 통지시간 이중 산정 | 접안이 먼저인데 NOR+6h를 그대로 적용 | min 규칙 | ASB-06-NOR-START 강제 | CLOCK |
| 4 | 이동 시간 공제 누락 또는 과다 | 선주는 산입, 용선주는 공제 주장 | 레이타임 중 공제, 체선 중은 쟁점 | ANCHOR_AWEIGH~ALL_FAST 구간 자동 분리, 체선 여부 표시 | CLOCK |
| 5 | 체선 중 레이타임 예외 적용 | 예외 조항을 체선에도 적용 | once on demurrage(The Spalmatori, The Nikmary) | 예외 조항 문구에 "demurrage" 명시 여부 확인 | CLAIM |
| 6 | 반액 체선료 과소·과다 적용 | 사유·기간 해석 차이 | 체선 중 해당 사유 기간만 반액. 레이타임 중 사유는 쟁점 | KMA 관측값으로 폭풍 기간 입증, OPS_STOPPED 사유 코드 | CLAIM |
| 7 | 펌핑 워런티 공제 시 육상 제한 입증 부재 | 터미널 배압·수용 기록 없음 | 입증 못 하면 공제 불가 | 터미널 배압·탱크 여유 기록과 펌핑 로그 대조 | CLAIM |
| 8 | 시효 도과·서류 미비 | 60/90일 경과, 서명 누락 | 청구권 소멸(The Abqaiq는 실질 충족 기준) | 시효 카운트다운, 필수 서류 체크리스트 | CLAIM |
| 9 | 시간대 혼동 | SOF UTC, 계약 현지시각 | 현지시각 기준 | 모든 ts에 tz 표기, 변환 로그 | INTAKE |
| 10 | 총량 레이타임 vs 항구별 혼동 | 가역 레이타임에서 선적항 사용량 누락 | 선적항 계산서 필요 | 선적항 SOF 요구, 없으면 가정 표시 | CLOCK |
| 11 | 매매계약·용선계약 불일치(갭) | 허용시간·요율·시효가 다름 | 각각 계산 | 레이어별 계산서 2장, 차액 표시 | CLAIM |
| 12 | 요율 단위·반올림 | 일 vs 시간, 분 단위 처리 | 분 단위 비례 | 소수 시간 계산, 표시만 반올림 | CLOCK |
| 13 | 용선주 지시 이동의 산입 혼동 | 첫 이동(제외)과 선석 간 이동(산입) 혼동 | cl.7 vs cl.9 | 이동 유형 코드(FIRST_BERTHING, CHTR_ORDER) | CLOCK |
| 14 | 대리점의 "accepted" 서명 | 무효 NOR의 하자 포기로 해석될 위험 | 사실관계 따라 waiver 인정 가능(The Happy Day) | 수령 문구 템플릿 "received, validity reserved" 권고 | COMMS |
| 15 | 서류 대기 시간 미반영 | 서식별 규정 상이 | 서식 규칙 따름 | HOSES_DISCONNECTED~DOCS_ON_BOARD 구간 별도 표시 | CLOCK |
| 16 | 야간 접안 제한·기상 대기를 "용선주 통제 밖"으로 처리 | cl.6 예외 문구 | reachable on arrival 위반으로 용선주 부담 쪽 판례 흐름(The Laura Prima, The Fjordaas) | 자동 판정 금지, 쟁점 배지 + 두 계산 | CLAIM |

---

## 2. 알아두면 좋은 판례 (영국법) [확인 필요 — 사건명·연도 대조]

| 사건 | 연도·법원 | 쟁점 | 교훈 |
|---|---|---|---|
| The Johanna Oldendorff | 1973, 귀족원 | 항구 용선에서 "도착선" 기준 | 항계 내 관습 대기장소에서 용선주의 즉시 처분 가능 상태면 도착(Reid test) |
| The Spalmatori (Union of India v Compania Naviera Aeolus) | 1964, 귀족원 | 체선 중 파업 예외 적용 여부 | once on demurrage, always on demurrage의 근거 |
| The Tres Flores | 1973, 항소법원 | 훈증 필요 상태의 NOR | 준비 완료는 "모든 면에서" 준비. 사소하지 않은 미비는 무효 |
| The Laura Prima | 1982, 귀족원 | Asbatankvoy cl.6 예외 vs cl.9 reachable on arrival | 선석 혼잡 대기는 용선주 부담. cl.6 예외는 용선주가 reachable 선석을 제공한 경우에만 |
| The Fjordaas | 1988, 상사법원 | 야간 항행 금지·기상으로 선석 접근 불가 | reachable on arrival는 혼잡 외 사유에도 적용 |
| The Sea Queen | 1988, 상사법원 | 예선·기상으로 접안 불가 | 같은 취지 |
| The Kyzikos | 1989, 귀족원 | WIBON의 적용 범위 | WIBON은 선석 혼잡에만 적용, 안개 등 항행 불가에는 미적용 |
| The Mexico I | 1990, 항소법원 | 무효 NOR이 나중에 유효해지는가 | 아니오. 재제출 또는 용선주 수락 필요 |
| The Petr Schmidt | 1998, 항소법원 | 허용 시간 밖에 낸 NOR | 내용이 진실하면 다음 허용 시각에 효력 |
| The Happy Day | 2002, 항소법원 | 무효 NOR 후 용선주가 이의 없이 하역 | 하역 개시 시점부터 레이타임(waiver·estoppel) |
| The Nikmary | 2003, 항소법원 | 체선 중 예외 조항 | 명시 없는 예외는 체선에 미적용 |
| The Eagle Valencia | 2010, 항소법원 | Shellvoy 5의 검역 6시간 조건 | 검역 허가 지연 시 NOR 무효, 청구 영향 |
| The Abqaiq | 2011, 항소법원 | BPVOY4 시효 조항의 서류 요건 | 서류의 "실질적 충족"이면 시효 차단 |

판례 요지는 P&I 클럽 해설과 Schofield 교재에서 다시 확인한다.

---

## 3. 학습 자료

### 3-1. 정의·표준
- BIMCO, *Laytime Definitions for Charter Parties 2013* — 용어 정의의 1차 출처. BIMCO 사이트에서 무료 열람.
- Asbatankvoy 서식 원문 — ASBA 발행. 검색으로 PDF 접근 가능(저작권 유의, 저장소 미포함).
- Shellvoy 6, BPVOY4(및 최신판) — 각사 발행. 원문 대조용.
- INTERTANKO Q88 양식 — 선박 제원 필드 학습.

### 3-2. 교재
- John Schofield, *Laytime and Demurrage* (Informa Law, 최신판) — 표준 교과서. 레이타임 개시·예외·체선료·시효를 판례와 함께 다룸.
- Donald Davies, *Commencement of Laytime* (Informa, 최신판) — 개시 시점 전문서.
- 김인현, *해상법* (법문사) — 국내 해상법 교재. 용선계약·정박기간 장 참조 [확인 필요: 판본].

### 3-3. 실무 해설(무료)
- P&I 클럽 Loss Prevention 자료: Gard, NorthStandard, Steamship Mutual, UK P&I Club, Skuld, West — "laytime", "demurrage", "notice of readiness"로 검색하면 사례 중심 해설이 많다.
- 해사 로펌 뉴스레터(HFW, Reed Smith, Ince, Stephenson Harwood 등)의 laytime/demurrage 판례 해설.
- 런던 중재 요약(London Arbitration summaries, Lloyd's Maritime Law Newsletter) — 탱커 체선료 쟁점의 실제 분포를 보여줌(유료).

### 3-4. 교육 과정
- Lloyd's Maritime Academy — Laytime & Demurrage 과정.
- ICS(Institute of Chartered Shipbrokers) — Tanker Chartering 교재.

### 3-5. 국내
- 한국해법학회지 — "정박기간", "체선료", "하역준비완료통지" 논문.
- 대한상사중재원 해사중재 사례, 한국해양진흥공사·KMI 보고서.
- 공공 API(핸드오프 §10): KHOA 조석, KMA 해양기상, KASI 출몰시각.

### 3-6. 시장의 유사 도구 [추론 — 벤치마크용, 상세 확인 필요]
- Veson Nautical IMOS의 laytime/demurrage 모듈, Voyager Portal, Shipamax 류의 체선료 관리·서류 추출 도구가 존재한다. 공통점은 **사후 클레임 처리 중심**이라는 것. 우리 차별점은 터미널 운영 시점의 실시간 노출·선석 순서 제안과 한국 공공데이터·SK 룰 연동이다(`08` 참조).

---

## 4. 현업 인터뷰 추가 질문 (체선료 특화)

1. SK가 용선주인 비중과 매매계약으로 부담하는 비중은? 연간 체선료 규모의 자릿수는?
2. 체선료 클레임은 누가(부서) 어떤 도구(엑셀·전용 SW)로 검토하나? 건당 소요 시간은?
3. 가장 자주 다투는 항목 3가지는? (이동 시간, NOR 유효성, 펌핑, 기상 반액, 서류 대기 중 무엇)
4. 야간 접안 제한·기상 대기 시간은 실제로 누가 부담하는 것으로 정산되나?
5. 터미널의 배압·탱크 여유·중단 기록은 어떤 형태로 남고 클레임 검토에 쓰이나?
6. 접안 순서를 바꿔 체선료를 줄인 경험이 있나? 무엇이 제약이었나(공정, 탱크, 도선, 안전)?
7. 표준 서식은 무엇을 주로 쓰나(Asbatankvoy·Shellvoy·BPVOY·자체)? 전형적 Rider는?
8. 비식별 SOF·타임시트·청구서 샘플을 받을 수 있나?
