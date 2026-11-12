# SEAGATE 진단 — 무엇을 하고, 어디가 비어 있고, 왜 이 프로젝트가 있나

- 작성일: 2026-11-02
- 용도: 팀 공유·다른 세션 인계용. [`seagate-handoff.md`](seagate-handoff.md)(2026-10-30)에서 "미확인"으로 남긴 로그인 뒤 기능을 확인하고, 체선료 Agent 방향(2026-11-02 기준 검토 중)에서 SEAGATE를 다시 읽은 문서
- 조사 범위: 비로그인 상태로 공개 페이지·사이트맵·개인정보처리방침을 브라우저로 직접 열람(자동 수집 없음) + 웹 기사. 계정 생성·로그인은 하지 않았다. **로그인 뒤 화면은 아무도 보지 못했고, 그 기능은 메뉴 이름으로 추정한 것이다.**
- 표기 규칙: **[사실]** 출처로 확인됨 / **[추론]** 사실에서 도출한 가설, 현업 검증 필요 / **[추천]** 의견·제안 (팀 확정 아님)

> **용어 메모**
> - **체선**: 선박이 선석을 기다리며 정박지에서 대기하는 것. 운영 개념이고 단위는 시간.
> - **체선료(demurrage)**: 계약에서 정한 하역 허용 시간(레이타임)을 넘겨 선박을 붙잡아 둔 대가로 선주(또는 매도자)에게 내는 돈. 계약 개념이고 단위는 금액.
> - **레이타임(laytime)**: 계약에서 정한 하역 허용 시간. 넘기면 체선료가 생긴다.
> - **NOR(Notice of Readiness)**: 선박이 하역 준비가 됐다고 알리는 통지. 보통 레이타임 계산의 출발점.
> - **SOF(Statement of Facts)**: 도착·접안·하역 시작·종료 등의 시각을 기록한 문서. 체선료 계산의 근거.
> - **ETB(Estimated Time of Berthing)**: 예상 접안 시각.
> - SEAGATE 메뉴는 "채선"으로 표기하지만 이 문서는 "체선"으로 쓴다.

---

## 0. 요약 — 먼저 읽을 것

1. **SEAGATE는 안내 사이트가 아니라 SK에너지 울산CLX의 부두 운영 시스템이다 [사실].** 공개 영역(회사소개·입항 가이드) 뒤, 로그인 전용 "SK Terminal"에 선석 예약·재고 예측·접안 계획·Berth Optimization·Berthing Simulation·체선 리포트 4종·Demurrage 요약이 있다.
2. **SK에너지 소유, SK AX 운영 [사실].** 정식 명칭은 "SK에너지 항무웹사이트". 개인정보보호담당자 소속은 SK에너지 생산조정팀이고, 운영은 SK주식회사 AX에 위탁했다. SKALA 운영사도 SK AX다.
3. **진단 [추론]:** 시스템은 기록·계산까지 하고, 그 사이의 판단·조율·서류 대조는 사람이 한다. 가장 큰 빈칸 후보는 **체선 '시간'(터미널이 재는 것)과 체선'료'(계약으로 정해지는 돈) 사이**다.
4. **프로젝트가 있는 이유 [추론]:** "SEAGATE가 쓸모없어서 맡겼다"보다는, SKALA의 현업 과제 구조에 SK AX가 운영하는 레거시 위에 AI 레이어를 얹는 아이디어 탐색이 겹친 것으로 보는 게 자연스럽다.
5. **방향 [추천]:** 체선 대시보드·최적화 솔버를 새로 만들지 않는다(이미 있다). SOF·NOR 대조, 레이타임 계산 초안, ETB 변경의 체선 영향 설명, 체선사유 분류처럼 '사이'를 메우는 에이전트를 노린다.
6. **바로 할 일:** §7의 질문 1~3을 멘토에게 먼저 묻는다. 이 답에 따라 §3의 가설과 §6의 방향이 바뀐다.

---

## 1. SEAGATE의 정체 [사실]

### 1-1. 누가 소유·운영하고 누가 쓰나

| 항목 | 내용 | 근거 |
|---|---|---|
| 정식 명칭 | SK에너지 항무웹사이트(SEAGATE) | 개인정보처리방침 |
| 개인정보보호담당자 소속 | SK에너지 생산조정팀 → 업무 오너 부서로 보임 [추론] | 처리방침 제7조 (사이트 하단 대표 전화와 같은 번호) |
| 운영 | SK주식회사 AX에 "SEAGATE 운영업무 위탁" | 처리방침 제2조 |
| 사용자 | 협력사·관계사 직원. 가입 시 사업자등록번호·회사명을 받고, 퇴사·직무이동 시 계정 삭제 → 대리점·검사기관 같은 B2B 파트너로 보임 [추론] | 처리방침 제1조 |
| 가입 | 무료, 개인정보 수집 동의 후 등록 | 가입(Join) 페이지 |
| 처리방침 개정 | 2026-10-27 시행 | 메인 공지 |
| 터미널 미션 | "정량, 정품질의 석유 및 화학 제품을 적기에 가장 싸고 안전하게 운영하는 것" | Marine Terminal 페이지 |
| 조직 표기 | SK 울산 CLX 생산본부 운영담당자 | Marine Terminal 페이지 |

- 구 사이트 `www.skseagate.com`(ASP)에서 현 사이트(하단 ⓒ 2020, 정적 파일 경로 `/static/skiaf/`)로 옮겨 왔다. 2020년 전후 SKIAF라는 프레임워크로 다시 만든 것으로 보인다 [추론].
- 미션의 "가장 싸고"에 체선료가 들어간다. 체선료 Agent를 이 미션에 연결해 설명할 수 있다 [추천].

### 1-2. 메뉴 전체 (공개 사이트맵, 2026-11-02 확인)

**공개 영역**: About Us(Company) · Port Information(Entry Guide 울산·인천, Mooring Facilities 울산·인천) · Community(MSDS, Notice, Site Link, Sitemap)

**로그인 전용 "SK Terminal"** (상단 메뉴의 SK Terminal을 누르면 로그인 화면으로 이동)

| 메뉴 | 하위 화면 | 경로 (`/view/seagate/ter/...`) |
|---|---|---|
| Berth Reservation | Berth Rez · 제품재고관리 · 원유재고예측 | `reserv/reservation`, `inventory/inventPrdt`, `inventory/inventOil` |
| Ship Vetting | – | `vetting/vetting01` |
| Ship Berthing | Order List · Berthing Schedule · 부두제약관리 · Berth Optimization · ETB Change Log | `berthing/orderList`, `berthSch`, `berthAdm`, `berthOpt`, `etbChangelog` |
| Cargo Working | – | `cargo/cargo01` |
| Performance Record | – | `record/record01` |
| Performance Summary | Cargo · Berth · Berth Share · **Demurrage** · Evaluate · Vessel Search | `summary/summary01`~`06` (Demurrage는 `summary04`) |
| Report | **체선리스트 · 체선지표 · 체선사유 · 주간체선** · 부두제약 · 선박사이즈 | `report/report05`, `01`, `02`, `06`, `03`, `04` |
| Ship Inspection | SK Safety Inspection · Pre-chartering Inspection · 연차검사 · 도입검사 | `inspection/inspection01`, `04`, `02`, `03` |
| Ship Particulars | – | `particular/particular01` |
| Berthing Simulation | – | `simulation/simul` |

- 상·하위 묶음은 사이트맵의 링크 패턴(상위 메뉴가 하위 화면 중 하나로 연결됨)으로 판단했다.
- 공개 Entry Guide(울산)에는 입출항 보고 절차만 있고 NOR·레이타임·체선 안내는 없다. 체선과 관련된 화면은 전부 로그인 뒤에 있다.

### 1-3. 메뉴를 업무 흐름에 다시 꿰면 [추론]

| 단계 | 업무 | SEAGATE 화면 |
|---|---|---|
| ① 예약 | 선석 예약을 탱크 재고(원유 받을 공간, 실어 보낼 제품)와 함께 본다 | Berth Rez, 원유재고예측, 제품재고관리 |
| ② 심사 | 선박 적격 여부, 검사 | Ship Vetting, Ship Inspection, Ship Particulars |
| ③ 계획 | 접안 순서·시간, 부두 제약, 최적화, 변경 이력 | Order List, Berthing Schedule, 부두제약관리, Berth Optimization, Berthing Simulation, ETB Change Log |
| ④ 하역 | 작업 진행, 실적 기록 | Cargo Working, Performance Record |
| ⑤ 사후 | 체선·실적 집계 | Performance Summary(Demurrage 포함), Report(체선 4종) |

→ 핸드오프 문서 §2가 그린 업무 흐름 ①~④가 SEAGATE 안에 이미 다 있다. 특히 ⑤에 체선 전용 리포트가 4개 있다는 점이 체선료 Agent 방향에 직접 영향을 준다.

---

## 2. 진단 ① — 눈에 보이는 문제 [사실]

| 증상 | 위치 |
|---|---|
| 템플릿 기본 문구 노출: "SKIAF에서 알려드립니다", "자주 묻는 질문들입니다" | Marine Terminal 페이지 (현재 메뉴·사이트맵에 없는 페이지) |
| HTML 태그가 글자로 노출: `Organization<br/>SK 울산 CLX 생산본부 운영담당자` | 같은 페이지 |
| 낡은 외부 링크: 해양수산부 옛 도메인 `momaf.go.kr` 여러 개 | Site Link |
| 깨진 링크: `http://http://www.mpa.gov.sg` | Site Link |
| 오타: 채선(→체선), Performancer Record, registred, Sagate | 사이트맵, 로그인, 공지 |
| 기능과 무관한 문구: 메인의 Berthing Plan 카드 설명이 "활발한 석유개발을 진행하여 에너지를 공급의 중심이 되겠습니다" | 메인 |
| 페이지 제목 오류: 가입 페이지 탭 제목이 "Contract" | Join |

**해석 [추론]:** 공개 영역은 새 투자 없이 유지보수 모드로 운영되고 있다. 결함 하나하나는 사소하지만 "개선 예산이 적은 레거시"라는 신호다. 그렇다면 개선안은 시스템을 다시 만들기보다 기존 시스템 위에 얹는 레이어가 현실적이다.

**주의:** 공개 영역의 품질로 로그인 뒤 업무 기능의 품질까지 판단할 수는 없다. 또 멘토가 SEAGATE 운영 쪽일 수 있으니, 이 표를 그대로 보여 주기보다 "레거시라 개선 여지가 있다" 정도로 말하는 편이 낫다 [추천].

---

## 3. 진단 ② — 구조적 문제 가설 [추론 — 로그인 뒤 미확인]

각 가설은 §7의 인터뷰 질문으로 검증한다.

### H1. 기록은 하지만 행동으로 이어지지 않는다
- 근거: 체선 리포트 4종이 Report 메뉴에 있는 사후 집계다. 체선사유가 별도 리포트라서, 사유 코드를 사람이 골라 입력할 가능성이 높다.
- 영향: 같은 사유의 체선이 반복돼도 다음 배선 결정에 자동으로 반영되지 않는다.
- 검증: §7 질문 2

### H2. 기능이 화면별로 쪼개져 있다
- 근거: 원유재고예측(Berth Reservation), Berthing Schedule·Optimization(Ship Berthing), Demurrage(Performance Summary)가 서로 다른 메뉴에 있다.
- 영향: "ETA가 12시간 늦어지면 탱크 재고, 후속 선박, 체선료는?" 같은 질문에 사람이 여러 화면을 오가며 답을 맞춘다.
- 검증: §7 질문 4

### H3. 입력이 비정형이다
- 근거 (업계 일반): NOR·SOF·Q88·ETA 변경은 메일·PDF·VHF로 들어온다. 웹 포털은 누군가 옮겨 적어야 한다.
- 영향: 체선료 정산의 핵심인 SOF 시각 대조가 수작업으로 남고, 오기·누락 위험이 있다.
- 검증: §7 질문 5

### H4. 체선 '시간'과 체선'료' 사이에 간극이 있다 ← 가장 중요
- 근거: 터미널이 재는 것은 대기 시간이다. 체선료는 용선계약(CP)이나 원유 매매계약의 레이타임·예외 조항(기상, 선석 이동, 선박 사유 지연 등)으로 계산된다. 계약은 터미널이 아니라 트레이딩·용선 조직이 가질 가능성이 높다(예: SEAGATE Company 페이지에 원유·제품 수출입 전문 자회사로 소개된 SK트레이딩인터내셔널).
- 영향: 터미널 체선 지표와 실제로 지급하는 체선료가 다를 수 있다. 클레임 검토가 시스템 밖(Excel·메일)에서 이뤄질 수 있다.
- 검증: §7 질문 1

### H5. 최적화 기능이 있어도 설명·조율은 사람 몫이다
- 근거: Berth Optimization·Berthing Simulation이 있고, 부두제약관리가 별도 화면이라 제약 조건을 사람이 관리하는 것으로 보인다. 업계 사례로 Vopak 친저우 터미널은 AI 배선 시스템 도입 전, 수작업 입력·흩어진 정보·선착순 규칙이 지연과 부서 간 분쟁을 만들었다고 밝혔다(도입 후 화주 체선료 20% 감소 — 업체 발표 수치).
- 영향: 최적화 결과를 대리점·생산·출하 쪽에 설명하고 합의하는 일이 남는다. 결과를 믿지 못하면 최적화 화면 자체가 안 쓰일 수 있다.
- 검증: §7 질문 3

---

## 4. 외부 환경 — 왜 지금 이 빈칸이 비싼가

| 시점 | 내용 | 출처 |
|---|---|---|
| 2026-04 | 호르무즈 해협 사실상 봉쇄. 국내 4대 정유사가 중동 원유에 크게 의존해 수급이 불안하고, 5월 재고 부족 우려 [사실] | Korea Times |
| 2026-07 | 울산항 액체화물 1,517만 톤(전년 동월 1,296만 톤, 17% 증가). 비중동산 원유와 호르무즈를 거치지 않은 UAE 원유 수입 증가 [사실] | 파이낸셜뉴스(울산항만공사 자료) |
| 2026-09 | 중동–중국 VLCC 용선료가 하루 120만 달러를 넘어 사상 최고. 지난해 대부분은 하루 2만~5만 달러였다 [사실] | SBS Biz(FT·브레마 자료 인용) |
| 2026-09 | SK이노베이션 울산CLX '듀얼 브레인'·'1인 1에이전트'. 적용 영역은 생산 최적화·설비 신뢰성·안전보건환경이고 부두·출하·물류 언급은 없다 [사실] | MTN |

**해석 [추론]:** 원유 도입선이 바뀌고 물량이 늘면 도착 일정이 흔들린다. 탱커 체선료 단가는 보통 계약 시점의 시장 운임을 따라가므로, 운임이 높은 시기에는 대기 1시간의 값도 크다. 그룹 AI 드라이브에서 부두·물류 영역은 아직 비어 있다.

---

## 5. 이 프로젝트가 존재하는 이유 [추론, 가능성 순]

| 순위 | 가설 | 근거 |
|---|---|---|
| 1 | **SKALA의 현업 과제 구조 + SK AX가 운영하는 시스템** | SKALA 최종 프로젝트는 "SK 현업 조직이 직접 제시한 문제"를 바탕으로 현업 인터뷰 → 주제 풀 선정 → 팀 구성 → 주제 선정 순으로 진행한다 [사실]. SKALA는 SK C&C(현 SK AX)가 2024년 말 1기를 모집하며 시작했고, SEAGATE 운영 위탁사도 SK AX다 [사실]. → SEAGATE를 운영하는 SK AX 쪽, 또는 고객인 SK에너지 생산조정팀이 "이 레거시에 AI를 얹으면?"을 주제로 냈을 가능성 |
| 2 | **그룹 AI 드라이브의 빈칸** | 듀얼 브레인·1인 1에이전트의 보도 적용 영역은 공정·설비·안전이다 [사실] → 부두·물류 쪽 에이전트 사례가 필요하다 |
| 낮음 | "SEAGATE가 쓸모없어서 맡겼다" | 교육생 프로젝트에 운영 시스템 교체를 맡기지는 않는다. 체선 리포트·최적화가 이미 있어 '없는 기능'을 메우려는 과제로 보기도 어렵다. 기대치는 아이디어·PoC 수준이고, 좋으면 SK AX가 고객 제안으로 가져갈 수 있다 |

**시사점 [추천]:** 멘토·심사위원이 볼 포인트는 "기존 SEAGATE를 이해했는가, 그 위에 무엇을 얹었는가"일 가능성이 크다. 발표는 SEAGATE 메뉴 구조로 시작해 "여기까지는 이미 있다 / 여기가 비어 있다"를 먼저 보여 준다.

---

## 6. 체선료 Agent 방향에 주는 의미 [추천]

### 6-1. 피할 것
- 체선 대시보드·KPI 화면을 새로 만들기 → Report(체선 4종)·Performance Summary(Demurrage)와 겹친다.
- 선석 최적화 솔버를 처음부터 만들기 → Berth Optimization·Berthing Simulation과 겹친다. 핸드오프 문서의 후보 C(접안계획 재조정)·E(하역실적·체선 분석)는 재평가가 필요하다.
- 접안 확정·클레임 확정을 에이전트가 자동으로 하기 → 책임 문제가 생기고 듀얼 브레인 취지(사람이 최종 결정)와도 어긋난다.

### 6-2. 노릴 자리 — SEAGATE의 기록과 계산 '사이'

| 에이전트 역할 | 메우는 빈칸 | SEAGATE와 닿는 곳 |
|---|---|---|
| SOF·NOR를 읽어 SEAGATE 기록과 대조 | H3, H4 | Cargo Working, Performance Record |
| 레이타임 계산 초안 + 근거(계약 조항·시각·예외) | H4 | Performance Summary > Demurrage |
| ETB 변경 1건의 체선 영향 설명("이 변경으로 체선 n시간, 약 $X") | H2, H5 | ETB Change Log, Berthing Schedule, 원유재고예측 |
| 체선사유를 증거와 함께 분류 | H1 | Report > 체선사유 |
| 담당자 승인(Human-in-the-loop) | 전체 | – |

### 6-3. 데이터
- 로그인 뒤 데이터를 받을 수 있을지는 불확실하다. 멘토에게 비식별 샘플(체선리스트, 체선사유 코드표, ETB Change Log, Demurrage 요약 화면 캡처)을 요청한다.
- 받을 수 없으면 합성 데이터 + 가정값 문서화로 간다(핸드오프 문서 §5-6 방식 유지).

---

## 7. 멘토·현업 인터뷰 질문 (우선순위 순)

1. Performance Summary의 Demurrage와 체선 리포트는 시간 지표인가요, 금액·클레임까지 다루나요? 체선료 정산은 누가 어떤 도구로 하나요? (H4)
2. 체선사유는 누가 언제 어떻게 입력하고, 그 데이터로 무엇을 결정하나요? (H1)
3. Berth Optimization·Berthing Simulation은 실제로 쓰이나요? 안 쓰인다면 이유는 무엇인가요? (H5)
4. ETB 변경은 얼마나 자주 일어나고, 누가 누구에게 어떻게 알리나요? 1건 처리에 시간이 얼마나 걸리나요? (H2)
5. NOR·SOF는 어떤 경로(메일·PDF·시스템)로 들어오고, SEAGATE 기록과 대조하나요? (H3)
6. 이 과제를 낸 곳은 SK에너지 생산조정팀인가요, SEAGATE를 운영하는 SK AX 팀인가요? 기대하는 결과물은 아이디어·PoC·실사용 중 어느 수준인가요? (§5)
7. 화면 캡처나 비식별 샘플(체선리스트, 체선사유 코드표, ETB Change Log)을 받을 수 있나요? (§6-3)

질문 1~3의 답에 따라 §3의 가설과 §6의 방향이 크게 바뀐다. 이 셋을 먼저 묻는다.

---

## 8. 핸드오프 문서(2026-10-30)와 달라진 점

| 핸드오프 문서 | 이번 확인 |
|---|---|
| §1-2 로그인 뒤 기능 "미확인", 메뉴는 구 사이트 검색 스니펫 기준 | 현 사이트 사이트맵으로 로그인 전용 메뉴 전체를 확인했다(§1-2) |
| §2 Pain point 4 "대기 시간 = 체선료" | SEAGATE가 체선을 이미 측정한다(리포트 4종·Demurrage 요약). 빈칸은 측정 이후다 |
| §4 후보 C(접안계획 재조정)·E(하역실적·체선 분석) | Berth Optimization·Simulation, 체선 리포트와 겹친다 → 재평가 필요 |
| §9 "멘토가 SK이노베이션 현업인지 SK AX 소속인지" | SEAGATE 운영 위탁사가 SK AX다 [사실] → SK AX 쪽 과제일 가능성 [추론] |
| §1-3 공개 운영 규칙(Entry Guide·안전규정) | 변동 없음 |

---

## 9. 출처

**SEAGATE (2026-11-02 비로그인 열람)**
- 사이트맵: https://skseagate.skinnovation.com/view/seagate/sys/sitemap/sitemap01
- 가입·개인정보처리방침: https://skseagate.skinnovation.com/view/seagate/sys/contact/contact
- Marine Terminal – Ulsan CLX: https://skseagate.skinnovation.com/view/seagate/abo/marinter/marinter01
- Site Link: https://skseagate.skinnovation.com/view/seagate/sys/sitelink/sitelink01
- 메인: https://skseagate.skinnovation.com/view/bcm/main
- Entry Guide – Ulsan CLX: https://skseagate.skinnovation.com/view/seagate/inf/entry/entry01
- Company: https://skseagate.skinnovation.com/view/seagate/abo/company/company01

**SKALA**
- SKALA 공식 사이트: https://www.2026skala.co.kr/
- SK AX, SKALA 광주·울산으로 확대: https://www.skax.co.kr/company/news-room/sk-ax-skala-%EA%B4%91%EC%A3%BC%C2%B7%EC%9A%B8%EC%82%B0%EC%9C%BC%EB%A1%9C-%ED%99%95%EB%8C%80%ED%95%B4-ai%EC%9D%B8%EC%9E%AC-%EC%9C%A1%EC%84%B1%ED%95%9C%EB%8B%A4
- SK C&C, 채용연계형 AI 교육과정 'SKALA' 1기 모집(바이라인네트워크, 2024-12): https://byline.network/2024/12/12-351/

**외부 환경**
- Korea Times(2026-04-02): https://www.koreatimes.co.kr/amp/business/companies/20260402/refiners-heavy-industries-continue-to-suffer-impact-of-iran-crisis
- 파이낸셜뉴스(2026-08-31): https://www.fnnews.com/news/202608311415049801
- SBS Biz(2026-09-23): https://biz.sbs.co.kr/amp/article/20000336533
- MTN(2026-09-15): https://news.mtn.co.kr/news-detail/2026091514285795364

**업계 사례**
- Vopak 친저우, 66 Yunlian AI 배선 시스템(LNG Industry, 2025-03-14): https://www.lngindustry.com/liquid-natural-gas/14032025/vopak-launches-66-yunlian-ai-powered-solution
