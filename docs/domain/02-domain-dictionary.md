# 체선료 도메인 용어 사전

- 작성일: 2026-11-02
- 범위: 탱커 항해용선의 레이타임·체선료, 그리고 SK 해상터미널 운영에서 그 시계에 영향을 주는 용어. 건화물 전용 용어는 "참고"로만 둔다.
- 1차 출처: BIMCO *Laytime Definitions for Charter Parties 2013*, Asbatankvoy Part II 원문, John Schofield *Laytime and Demurrage*. 판례 상세는 `07-pitfalls-and-resources.md`.
- 번역어는 국내 관행(정박기간·체선료·조출료 등)을 따르되 영문을 함께 쓴다. 팀 내 대화에서는 영문 용어를 그대로 쓰는 것을 권장한다 [추천] — 현업·계약서가 영문이기 때문이다.
- 표기: [사실] / [추론] / [확인 필요]. 표시가 없으면 표준 교재 수준의 일반 정의다.

## 읽는 법

| 열 | 뜻 |
|---|---|
| 모듈 | 이 용어를 주로 다루는 Agent 모듈. INTAKE(수집·파싱), CLOCK(레이타임 시계), EXPOSURE(노출 예측), SCHED(선석 순서), CLAIM(청구 검증), COMMS(보고·승인). `01-demurrage-primer.md` §5 참조 |
| 메모 | 수치, 예시, 쟁점, SEAGATE·울산 맥락 |

---

## A. 계약·당사자

| 용어 | 한글·약어 | 정의 | 메모 | 관련 | 모듈 |
|---|---|---|---|---|---|
| Charter Party | 용선계약(서), C/P | 선주가 선박의 운송 서비스를 용선주에게 제공하는 계약. 항해용선·정기용선·나용선으로 나뉨 | 체선료는 항해용선의 개념 | Voyage Charter | INTAKE |
| Voyage Charter | 항해용선 | 특정 화물을 A에서 B로 운송하기로 하고 운임을 받는 계약. 항만 체류 시간의 위험을 레이타임·체선료로 배분 | 표준서식: Asbatankvoy, Shellvoy, BPVOY | Laytime | INTAKE |
| Time Charter | 정기용선 | 기간 단위로 선박을 빌리고 용선료(hire)를 내는 계약. 항만 지연 위험을 용선주가 용선료로 부담하므로 체선료 개념이 없음(참고) | — | Hire | — |
| Owner / Disponent Owner | 선주 / 처분권 선주 | 선박 소유자, 또는 정기용선으로 빌린 배를 다시 항해용선으로 내주는 자 | 체선료 청구 주체 | Charterer | CLAIM |
| Charterer | 용선주 | 선박을 빌린 자. 항해용선에서 레이타임 초과분을 지급할 의무 | SK가 용선주인 경우 직접 부담 | Owner | CLAIM |
| Shipper / Receiver (Consignee) | 송하인 / 수하인 | 화물을 선적하는 자 / 받는 자. 터미널 지연의 실제 원인 제공자인 경우가 많음 | 매매계약 당사자와 겹침 | Sales Contract | INTAKE |
| Ship Agent | 선박대리점 | 항구에서 선주·용선주를 대리해 입출항 수속, NOR 전달, SOF 작성을 수행 | SEAGATE의 주 이용자 | SOF, NOR | INTAKE |
| Shipbroker | 용선중개인 | 선주·용선주 사이의 계약 성립을 중개하고 계약 요약(recap)을 작성 | — | Fixture | — |
| Fixture / Recap | 계약 성립 / 계약 요약 | 선박·화물·레이캔·운임·레이타임·체선료율 등 주요 조건의 합의와 그 요약본 | 계약조건 파싱의 1차 소스 | Charter Party | INTAKE |
| Rider Clauses | 추가 조항 | 표준서식 Part II에 덧붙이는 당사자 맞춤 조항. 펌핑 워런티·시효가 흔히 여기 있음 | 룰셋은 표준과 rider를 함께 봐야 함 | Pumping Warranty | INTAKE |
| Sales Contract / GTC | 매매계약 / 일반거래조건 | 원유·제품 매매계약. 레이타임·체선료 조항을 포함하며 보통 용선계약과 back-to-back | 메이저사 GTC는 공개되어 학습 자료로 쓸 수 있음 | Back-to-back | CLAIM |
| Back-to-back | 연동 전가 | 매매계약 체선료 조건을 용선계약과 맞춰 손실 없이 전가하는 구조 | 조건이 어긋나면 "체선료 갭"이 생김 | — | CLAIM |
| Incoterms (FOB / CFR / CIF / DES·DAP) | 인도조건 | 누가 선박을 수배하고 어느 시점에 위험이 넘어가는지를 정하는 조건. 누가 용선주인지를 결정 | `01` §3 표 | Charterer | INTAKE |
| Worldscale (WS) | 월드스케일 | 탱커 운임 산정의 표준 지수. 기준운임(flat rate)의 백분율로 운임을 표시. 기준 계산에 레이타임 72시간 가정이 포함 | 체선료율은 별도 협상 | Freight | — |
| Freight | 운임 | 항해용선의 대가. 체선료와 별개 | — | — | — |
| Deadfreight | 부적운임 | 약속 수량보다 적게 선적했을 때의 손해배상(참고) | — | — | — |

## B. 시간·레이타임

| 용어 | 한글·약어 | 정의 | 메모 | 관련 | 모듈 |
|---|---|---|---|---|---|
| Laytime | 레이타임, 정박기간 | 선적·양하를 위해 용선주에게 허용된 시간 | 탱커 보통 총 72 running hours | Allowed Laytime | CLOCK |
| Running Hours / Days | 연속 시간 | 중단 없이 연속으로 세는 시간 단위(SHINC 성격) | 탱커 표준 | SHINC | CLOCK |
| Allowed Laytime | 허용 레이타임 | 계약상 허용 시간. 총량(선적+양하) 또는 항구별 | 매매계약은 항구별(예: 36h)인 경우가 많음 [추론] | Reversible | CLOCK |
| Reversible Laytime | 가역 레이타임 | 선적항·양하항 레이타임을 합산해 쓰는 방식. 한쪽에서 남긴 시간을 다른 쪽에서 사용 | Asbatankvoy의 "total laytime"은 사실상 가역 | Non-reversible | CLOCK |
| Non-reversible / Average Laytime | 비가역 / 평균 | 항구별로 따로 계산 / 항구별 초과·절약을 상계 | 건화물에 흔함 | — | CLOCK |
| SHINC / SHEX | 일요일·공휴일 포함 / 제외 | 레이타임에 일·공휴일을 세는지 여부 | 탱커 running hours는 사실상 SHINC. 중동은 FHINC/FHEX(금요일) | — | CLOCK |
| Weather Working Day (WWD) | 기상 작업일 | 날씨가 허락하는 작업일만 세는 건화물 단위(참고) | 탱커에는 거의 없음 | SHEX | — |
| Laycan (Laydays / Cancelling) | 레이캔 | 선박이 선적 준비를 마쳐야 하는 기간. 시작일 전에는 레이타임이 개시되지 않고, 종료일을 넘기면 용선주에게 해지권 | 입항 일정의 첫 제약 | NOR | INTAKE |
| ETA Notices | 도착예정 통지 | 72/48/24시간 전 등 계약이 정한 사전 통지. 미이행 시 레이타임 개시를 늦추는 조항이 있음 | 터미널 접안계획의 입력값 | NOR | INTAKE |
| Notice Time | 통지시간 | NOR 후 레이타임 개시까지의 유예. 탱커 서식 6시간 | 접안이 먼저면 그 시점에 개시 | NOR | CLOCK |
| Commencement of Laytime | 레이타임 개시 | 유효 NOR + 통지시간 경과, 또는 접안 완료 중 빠른 때 | 분쟁이 가장 많은 지점 | Valid NOR | CLOCK |
| Cessation / Completion of Laytime | 레이타임 종료 | 탱커는 호스 분리 시점. 서식에 따라 서류 대기 시간을 산입 | — | Hoses Disconnected | CLOCK |
| Shifting (Time) | 이동(시간) | 묘박지→선석, 선석→선석 이동. 첫 이동은 레이타임 제외, 용선주 지시 이동은 산입(Asbatankvoy) | 체선 중에는 산입 가능성 [쟁점] | Deductions | CLOCK |
| Excepted Periods / Exceptions | 제외 기간 / 면책 | 레이타임에서 빼는 시간. 명시가 없으면 체선 시간에는 미적용 | Once on Demurrage | CLOCK |
| Unless Used (UU) / Even If Used (EIU) | 사용 시 산입 / 사용해도 제외 | 제외 기간에 실제로 작업했을 때 세는지 여부(건화물 관용구) | — | SHEX | — |
| Time Lost Waiting for Berth to Count as Laytime | 선석 대기 시간 산입 | 선석 용선에서 대기 시간을 레이타임으로 세게 하는 조항 | WIBON과 유사 효과 | Berth Charter | CLOCK |
| Turnaround Time | 체항 시간 | 도착부터 출항까지 총 시간. 터미널 KPI | 체선료와 상관이 높음 | Waiting Time | EXPOSURE |

## C. 도착·NOR

| 용어 | 한글·약어 | 정의 | 메모 | 관련 | 모듈 |
|---|---|---|---|---|---|
| Arrived Ship | 도착선 | 레이타임 개시의 전제. 항구 용선이면 항계 내 관습 대기장소에서 용선주의 즉시 처분이 가능한 상태(Reid test, The Johanna Oldendorff) | — | Port Charter | CLOCK |
| Port Charter / Berth Charter | 항구 용선 / 선석 용선 | 목적지가 항구인지 특정 선석인지. 선석 용선은 선석 도착 전 대기 위험이 선주에게 | WIBON 등으로 완화 | Arrived Ship | INTAKE |
| Customary Anchorage | 관습적 묘박지 | 해당 항구에서 통상 대기하는 장소. Asbatankvoy의 NOR 제출 장소 | 울산 E-1~E-3 묘박지 등 | NOR | CLOCK |
| Reachable on Arrival | 도착 즉시 접근 가능 | 용선주가 도착 즉시 갈 수 있는 선석을 제공할 의무. 혼잡·야간 제한·기상으로 못 가면 용선주 책임(The Laura Prima, The Fjordaas) | SK 선석 대기의 핵심 조항 | Always Accessible | CLOCK |
| Always Accessible | 항시 접근 가능 | 유사한 의무. 일부 해석은 출항 접근성까지 포함 | — | Reachable on Arrival | CLOCK |
| Notice of Readiness (NOR) | 하역준비완료통지 | 도착과 준비 완료의 통지. 유효 요건: 도착선 + 물리적·법적 준비 + 계약이 정한 방식 | 무효 NOR은 효력이 없음(The Mexico I) | Valid NOR | CLOCK |
| Valid / Invalid NOR | 유효 / 무효 NOR | 요건 충족 여부. 무효면 재제출 전까지 레이타임이 개시되지 않음. 단 용선주가 이의 없이 하역을 시작하면 그 시점에 개시(The Happy Day) | AIS 도착 시각 대조로 검증 | Waiver | CLOCK |
| Readiness (Physical / Legal) | 준비 완료(물리 / 법적) | 탱크·펌프·장비 준비 / 검역·세관 등 법적 허가 | 검역 미필도 무효 사유가 될 수 있음 | Free Pratique | CLOCK |
| Free Pratique | 검역 허가 | 보건 당국의 입항 허가. WIFPON이면 미취득 상태의 NOR 허용 | 일부 서식은 6시간 내 취득을 조건으로 함(The Eagle Valencia) | WIFPON | CLOCK |
| WIBON / WIPON / WIFPON / WCCON | 선석·항구·검역·통관 여부 무관 | NOR을 선석 밖·항구 밖·검역 전·통관 전이라도 낼 수 있게 하는 관용구 | WIBON은 혼잡 사유에만 적용(The Kyzikos) | NOR | CLOCK |
| Waiver / Acceptance of NOR | NOR 하자 포기 / 수락 | 용선주가 무효 NOR을 알고도 받아들이거나 행위로 하자를 포기하는 것 | 대리점의 "accepted" 서명 효력이 쟁점 | Valid NOR | CLAIM |
| Re-tender | 재제출 | 무효 NOR 후 요건을 갖추어 다시 제출 | 선장 실무 포인트 | NOR | CLOCK |

## D. 체선료·정산

| 용어 | 한글·약어 | 정의 | 메모 | 관련 | 모듈 |
|---|---|---|---|---|---|
| Demurrage | 체선료 | 레이타임 초과 시간에 대한 약정 배상 | — | Laytime | CLAIM |
| Demurrage Rate | 체선료율 | USD/일로 표시하고 시간 비례로 정산 | 시장 연동, 협상 | Pro Rata | CLOCK |
| Pro Rata | 비례 배분 | 하루 미만은 시간·분 비례 | 분 단위 계산 관행 | — | CLOCK |
| Once on Demurrage, Always on Demurrage | 일단 체선은 계속 체선 | 체선 개시 후에는 레이타임 예외가 적용되지 않는다는 원칙(명시적 문구가 없는 한) | The Spalmatori, The Nikmary | Exceptions | CLOCK |
| Half-rate Demurrage | 반액 체선료 | 화재·폭풍·파업·용선주 측 플랜트 고장 등으로 생긴 체선은 50% | Asbatankvoy cl.8 | — | CLOCK |
| Despatch (Dispatch) | 조출료 | 절약한 레이타임에 대한 보상. DHD = 체선료율의 절반 | 탱커에는 보통 없음 | Demurrage | — |
| Deductions | 공제 | 선주 귀책·계약상 제외 시간 | shifting, 펌핑 미달, 고장 | Exceptions | CLAIM |
| Pumping Warranty | 펌핑 보증 | 전량을 24시간 내 양하하거나 매니폴드 100 psi를 유지한다는 선주 보증. 미달 시 초과 시간은 선주 부담 | 터미널의 "육상 제한 없음" 입증이 필요 | Excess Pumping Time | CLAIM |
| Excess Pumping Time | 초과 펌핑 시간 | 보증 대비 초과분. 레이타임·체선에서 공제 | 펌핑 로그·압력 기록 | Pumping Warranty | CLAIM |
| Fault of the Owner / Vessel | 선주·선박 귀책 | 선박 측 원인의 지연. 레이타임·체선 모두에서 제외(일반 원칙) | 고장, 선원 파업 | Deductions | CLAIM |
| Time Bar | 청구 시효(실권 기한) | 체선료 청구와 서류 제출의 기한. 넘기면 청구권 소멸 | Shellvoy 6: 통지 60일·서류 90일, BPVOY4: 90일 [확인 필요] | Supporting Documents | CLAIM |
| Supporting Documents | 증빙 서류 | NOR, SOF, 타임시트, 펌핑 로그, 항의서 등 청구에 필수인 서류 | 서식마다 목록이 다름 | Time Bar | CLAIM |
| Letter of Protest (LOP) | 항의서 | 지연·조건에 대한 이의 기록. 책임 소재 분쟁의 증거 | 터미널도 발행 | SOF | CLAIM |
| Demurrage Claim | 체선료 청구 | 선주→용선주, 또는 매매계약 당사자 간 청구서 | 계산서 포함 | Settlement | CLAIM |
| Settlement / Counter-claim | 합의 / 반대청구 | 협상 후 합의액 확정 / 상대방 과실분 역청구 | — | — | CLAIM |
| Demurrage Exposure | 체선료 노출 | 아직 확정되지 않았지만 현재 계획대로면 발생할 체선료 예측액 | 우리 Agent의 핵심 KPI | — | EXPOSURE |

## E. 문서

| 용어 | 한글·약어 | 정의 | 메모 | 관련 | 모듈 |
|---|---|---|---|---|---|
| Statement of Facts (SOF) | 사실기록서 | 입항~출항의 사건·시각 기록. 선장·대리점·터미널 서명 | 1차 증빙 | Time Sheet | INTAKE |
| Time Sheet | 타임시트 | SOF를 바탕으로 레이타임 개시·공제·종료를 표로 계산한 것 | — | Laytime Statement | CLOCK |
| Laytime Statement / Calculation | 레이타임 계산서 | 사용 시간 대 허용 시간, 체선료 산출 | `04` 예제 양식 | Time Sheet | CLOCK |
| NOR Form | NOR 양식 | 제출 시각·수령 시각·서명 | 수령(received) 시각이 기준 | NOR | INTAKE |
| Port Log / Deck Log | 항해일지 | 선박 공식 기록. SOF 검증에 사용 | — | SOF | CLAIM |
| Pumping Log | 펌핑 로그 | 시간별 매니폴드 압력·유량 | 펌핑 워런티 판단 | Pumping Warranty | CLAIM |
| Ullage Report | 얼리지 보고서 | 탱크 액면·수량 측정 기록 | 하역 시작·종료 확정 | — | INTAKE |
| Bill of Lading (B/L) | 선하증권 | 화물 수령 증권. 서류 지연이 출항 대기의 원인이 되기도 함 | — | — | — |
| Q88 | 선박 제원 질의서 | 탱커 표준 제원 양식(INTERTANKO). DWT·LOA·흘수·매니폴드·펌프 능력 | SEAGATE Ship Particulars에 대응 | Vessel | INTAKE |
| Hose Connection / Disconnection Record | 호스 연결·분리 기록 | 레이타임 종료 기준 시각 | 터미널 기록이 권위 있음 | Cessation | CLOCK |

## F. 터미널 운영

| 용어 | 한글·약어 | 정의 | 메모 | 관련 | 모듈 |
|---|---|---|---|---|---|
| Berth / Pier / Dolphin / SBM | 선석 / 부두 / 돌핀 / 단일점 계류부이 | 접안 시설 유형. SBM은 해상 부이에 계류해 해저 배관으로 하역 | 울산 SK2·SK3 Buoy = SBM | Mooring Facilities | SCHED |
| Berthing Plan / Berth Window | 접안계획 / 접안 시간창 | 선석별 선박 배정과 시각 | SEAGATE Berthing Plan | — | SCHED |
| ETB (Estimated Time of Berthing) | 예상 접안 시각 | 접안계획상 선박이 선석에 붙을 것으로 보는 시각. ETA·앞 선박 종료·접안 규칙으로 정해짐 | SEAGATE Ship Berthing에 ETB Change Log가 있음 [사실, 메뉴명] | Berthing Plan | SCHED |
| ETB Change (Log) | ETB 변경 (이력) | 접안 예정 시각의 변경과 그 이력. 변경 1건이 후속 선박의 대기·체선료를 연쇄적으로 바꿈 | 우리 Agent의 "변경 1건 → 돈" 설명 대상 | ETB | EXPOSURE |
| 체선(대기) vs 체선료 | — | **체선**은 선박이 선석을 기다리며 정박하는 운영 개념(단위: 시간). **체선료**는 계약상 레이타임 초과에 대해 지급하는 돈(단위: 금액). 둘은 같지 않다 | SEAGATE Report의 체선 4종·Performance Summary의 Demurrage는 전자(시간 지표)일 가능성 [추론, 인터뷰로 확인] | Demurrage Exposure | CLOCK |
| 체선사유 (코드) | Waiting / Delay Reason Code | 체선이 생긴 원인 분류(선석 점유, 기상, 야간 제한, 탱크 여유, 선박 사유 등). SEAGATE Report에 체선사유 리포트가 있음 | 사람이 입력하는 코드로 추정. 증거 기반 자동 분류가 Agent 과제 | OPS_STOPPED 사유 | CLAIM |
| 부두제약 (Berth Constraints) | — | 선석별 접안 제약(크기·화물·주야간·기상). SEAGATE에 부두제약관리 화면과 리포트가 있음 | 우리 룰셋(ULS-*)의 현업 원본일 가능성 | Rule ID | SCHED |
| Berth Occupancy / Utilization | 선석 점유율 | 선석이 사용 중인 시간 비율 | 높을수록 대기 증가 | Congestion | EXPOSURE |
| Congestion | 혼잡 | 선석 부족으로 대기 발생 | reachable on arrival 쟁점 | Waiting Time | EXPOSURE |
| Waiting Time (at Anchorage) | 묘박 대기 시간 | 도착~이동 시작 | 레이타임에 산입되는 핵심 시간 | Laytime | CLOCK |
| Pilotage / Tugs | 도선 / 예선 | 접·이안 보조. 울산 SK 선석은 강제 도선 | 가용성이 접안 시각을 결정 | Shifting | SCHED |
| All Fast / Finished Mooring | 접안 완료 / 계류 완료 | 모든 계류줄 고정(부두) / 계류 완료(SBM). 레이타임 개시의 대안 시점 | — | Commencement | CLOCK |
| First Line / Last Line | 첫 줄 / 마지막 줄 | 접안·이안의 시작·끝 기준 | SOF 표준 항목 | All Fast | INTAKE |
| Hoses Connected / Disconnected | 호스 연결 / 분리 | 하역 준비 완료 / 하역 종료 기준 | 레이타임 종료 | Cessation | CLOCK |
| Manifold | 매니폴드 | 선박 측 배관 연결부. 압력 측정 지점 | 100 psi 기준점 | Pumping Warranty | CLAIM |
| Discharge Rate / Back Pressure | 양하 속도 / 배압 | 시간당 양하량 / 육상 배관 저항. 배압이 높으면 육상 제한 | 펌핑 분쟁의 핵심 | Pumping Log | CLAIM |
| Shore Tank Availability (Ullage) | 육상 탱크 여유 | 받을 탱크 용량. 부족하면 양하 중단(용선주 사유) | 공정 일정과 연결 | Deductions | EXPOSURE |
| Line Displacement / Clearing | 라인 치환 | 배관 내 잔류물 밀어내기. 요구 시 레이타임 산입(Asbatankvoy cl.10) | — | — | CLOCK |
| Ship/Shore Safety Checklist (SSSCL) | 선박·육상 안전점검표 | 하역 전 공동 점검. 미충족 시 하역 불가 | SK 안전규정 | — | INTAKE |
| Daytime Berthing Restriction | 주간 접안 제한 | 일정 규모 이상 선박은 주간에만 접안(울산 SK3~8) | "주간" 정의 [확인 필요] | Night Mooring Prohibition | SCHED |
| Night Mooring Prohibition (SBM) | SBM 야간 계류 금지 | SK 부이는 야간 계류 불가 | 체선료 발생의 주요 원인(가설) | Daytime Berthing Restriction | SCHED |
| UKC (Under Keel Clearance) | 여유 수심 | 선저와 해저 사이의 여유. 조석과 함께 접안 가능 시간을 결정 | 기준값 [확인 필요] | Tide Window | SCHED |
| Tide Window | 조석 시간창 | 흘수 제한 선박이 접안 가능한 조위 구간 | KHOA 조석 API | UKC | SCHED |
| Weather Limits | 기상 한계 | 풍속·파고 기준 초과 시 접안·하역 중단 | 수치 미공개 → 현업 확인 | Half-rate Demurrage | EXPOSURE |
| Cargo Operations (Ops) | 하역 작업 | 선적·양하의 실작업 시간 | 선박·육상 능력 중 작은 쪽이 결정 | Discharge Rate | CLOCK |

## G. 검사·규제 (참고, `../seagate-handoff.md`와 연결)

| 용어 | 한글·약어 | 정의 | 메모 | 관련 | 모듈 |
|---|---|---|---|---|---|
| Vetting / SIRE 2.0 | 선박 적합성 심사 / OCIMF 검사 제도 | 화주·터미널이 선박 안전성을 심사. 지연되면 접안 지연 | 핸드오프 §5 | — | INTAKE |
| PSC | 항만국 통제 | 국가 당국의 선박 검사. 억류 시 대기 | — | — | — |
| Sanctions Screening | 제재 스크리닝 | 제재 대상 선박·화주 확인 | 2026년 제재 유조선 급증 | — | INTAKE |

## H. Agent·데이터

| 용어 | 한글·약어 | 정의 | 메모 | 관련 | 모듈 |
|---|---|---|---|---|---|
| Rule Engine / Rule ID | 룰 엔진 / 룰 식별자 | 계약·터미널 규칙을 데이터로 관리하고 결정론적으로 판정 | `05` 룰 목록 | Provenance | CLOCK |
| Provenance / Evidence | 출처 / 근거 | 판정마다 붙는 출처(조항·SOF 행·API 조회 시각) | 핸드오프 원칙 | Rule ID | 전체 |
| What-if Scenario | 가정 시나리오 | 접안 순서·선석 변경 시 비용 비교 | 시뮬레이터의 핵심 | Objective Function | SCHED |
| Objective Function | 목적함수 | 최적화 기준. 예: 총 체선료 노출 최소화 + 규칙 위반 0 + 대기 가중합 | 가중치는 현업과 합의 | — | SCHED |
| Human-in-the-loop (HITL) | 사람 승인 루프 | Agent는 제안, 확정은 담당자 | 듀얼 브레인 | — | COMMS |
| Golden Set | 정답 세트 | 계산 예제·SOF와 정답 체선료의 쌍. 평가용 | `04` 예제가 씨앗 | — | 평가 |
| MCP Tool | MCP 도구 | 룰 엔진·KB·공공 API를 Agent가 호출하는 표준 인터페이스 | 핸드오프 §5-4 | — | 전체 |

---

## 확인 필요 목록 (현업 인터뷰·원문 대조 후 갱신)

| 항목 | 현재 상태 | 확인 방법 |
|---|---|---|
| Time Bar 일수(Shellvoy 6 60/90일, BPVOY4 90일) | 교재 기억 기반 | 서식 원문 대조 |
| 서류 대기 시간 산입 규정(호스 분리 후) | 서식별 상이 | Shellvoy·BPVOY 원문 |
| 체선 중 shifting 시간 산입 여부 | 쟁점 | 계약 문구 + 중재 사례 |
| "주간"의 정의(울산 SK3~8, SBM) | 미공개 | 현업 |
| UKC 기준, 기상 한계 수치 | 미공개 | 현업 |
| SK의 전형적 계약 구조(FOB/DES 비중, 자가 용선 여부) | 가설 | 현업 |
| 매매계약 레이타임 허용치(예: 36h) | 업계 관행 추정 | GTC 원문·현업 |
