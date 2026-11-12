# SEAGATE(SK 해상터미널 포털) 레퍼런스 분석 & SKALA 최종 프로젝트 방향

- 작성일: 2026-10-30
- 용도: 다른 세션·팀원에게 그대로 넘기는 컨텍스트 문서 (이 문서만 읽고 이어서 작업할 수 있게 작성)
- 표기 규칙: **[사실]** 출처로 확인됨 / **[추론]** 사실에서 도출한 가설, 현업 검증 필요 / **[추천]** 의견·제안 (팀 확정 아님)

> **2026-11-02 업데이트**: 프로젝트 초점이 **체선료(demurrage) 최적화 Agent**로 좁혀졌다. 이 문서의 §4~§5(Pre-Arrival Agent 추천)는 배경 자료로 유지하되, 현재 방향·도메인 학습 자료·SEAGATE와의 차이는 `domain/00-README.md`부터 읽을 것. 체선(pain point 4, 후보 E)이 핵심으로 올라왔고, Pre-Arrival 검토 요소(선석 적합성·야간 접안 규칙·기상 시간창)는 체선료 노출 계산의 입력으로 재사용된다.

> **2026-11-02 갱신:** 로그인 뒤 메뉴 전체와 운영 주체(SK에너지 생산조정팀 소유, SK AX 운영)가 확인되어 §1-2·§2·§4·§9 일부가 낡았습니다. 달라진 점은 [seagate-diagnosis.md](seagate-diagnosis.md) §8을 먼저 보세요.

---

## 0. 핸드오프 요약 — 다른 세션은 여기부터 읽을 것

1. **사용자 의도 [사실]**: 사용자가 아래 URL을 SKALA 최종 프로젝트의 관련 레퍼런스로 지정했고, "이 사이트에서 사용될" 프로젝트를 구상 중이다. 주제는 아직 팀 확정 전.
   - https://skseagate.skinnovation.com/view/seagate/abo/company/company01
2. **SEAGATE의 정체 [사실]**: 링크된 페이지 자체는 SK이노베이션 회사소개지만, 사이트 전체는 **SK 해상터미널(Marine Terminal) 대외 포털**이다. 울산CLX·인천CLX에 입출항하는 선박 측(선장·선박대리점·선주/용선주)을 위해 입항 가이드(Entry Guide), 계류시설 제원(Mooring Facilities), 터미널 안전규정을 공개하고, 메뉴에 Ship Vetting · Ship Berthing(Berthing Plan) · Cargo Working · Performance Record · Ship Particulars · Notice · MSDS가 있으며 회원 로그인이 있다. (로그인 뒤 기능의 실체는 미확인)
3. **추천 방향 [추천]**: **"SEAGATE Pre-Arrival Agent"(가칭)** — 입항 요청(노미네이션) 1건이 들어오면 에이전트가 ① 선박 서류 파싱 → ② 선석 적합성·야간접안 규칙 판정 → ③ Vetting·제재 스크리닝 → ④ 조석·기상·일출 기반 접안 가능 시간창 → ⑤ 근거가 붙은 검토 보고서와 대리점 회신 초안까지 만들고, **최종 승인은 터미널 담당자**(Human-in-the-loop). 도구는 MCP 서버로 분리.
4. **왜 이 방향인가 [사실 근거]**: SK이노베이션이 2026년 9월 울산CLX에 공개한 '듀얼 브레인'(AI 분석·제안 + 사람 최종결정)·'1인 1에이전트' 방향과 일치 / 2026년 VLCC 용선료 사상 최고·제재 유조선 급증 → 선박 대기와 Vetting 실수의 비용이 매우 큼 / 단순 RAG 챗봇과 차별화.
5. **바로 할 일**: (1) §7 질문으로 멘토·현업 인터뷰 → pain point 검증 (2) 데이터 제공 범위 확인(불가하면 합성 데이터 + 가정값 문서화) (3) MVP 범위 동결 후 공공 API 키 발급 — **기상청 해양기상관측 API는 개발계정도 심의승인이므로 가장 먼저 신청**.
6. **미확정 [확인 필요]**: 공식 과제정의서 유무, 팀 인원·기간, 멘토 소속, 제공 LLM/인프라 (§9).

> 새 세션에서는 "프로젝트 문서 `seagate-handoff.md` 기준으로 이어서" 라고 시작하면 된다.

---

## 1. SEAGATE는 무엇인가 [사실]

### 1-1. 정체와 범위
- 도메인: `skseagate.skinnovation.com` (SK이노베이션 도메인). URL 패턴: `/view/seagate/abo/...`(About), `/view/seagate/inf/...`(Port Information), 정적 PDF `/static/skiaf/download/...`
- 대상 터미널
  - **울산CLX**: SK에너지 운영 부두(SK1~SK8 Pier, SK2·SK3 Buoy) — "Entry Guide - Ulsan CLX"
  - **인천CLX**: SKIPC(SK인천석유화학) Marine Terminal — "Entry Guide - Incheon CLX"
- 구 사이트 `www.skseagate.com`(ASP)이 있었고, 현 사이트로 이전된 것으로 보임 [추론]

### 1-2. 메뉴 구조 (구 사이트 검색 스니펫 기준 — 신 사이트에서 직접 재확인 필요)
- **[사실] 스니펫에 나열된 메뉴 항목(순서 그대로)**: About Us · Company · Marine Terminal · Port Information · Entry Guide · Mooring Facilities · SK Terminal · Ship Vetting · Ship Berthing · Cargo Working · Performance Record · Performance Summary · Ship Particulars · Community · Notice · MSDS · Site Link / 메인 화면 Berthing Plan 위젯 / 계정 메뉴(Login · Join · Find Account · My info · Admin Login)
- 평면 목록이라 **상·하위 관계는 미확인**. 아래는 기능 성격별로 묶은 것 [추론]:

| 묶음 | 항목 | 추정 성격 |
|---|---|---|
| 회사·터미널 소개 | About Us, Company, Marine Terminal | 정보 |
| 입항 정보 | Port Information, Entry Guide, Mooring Facilities | 정보(가이드·제원) |
| 터미널 절차 | SK Terminal(안전규정 포함), Ship Vetting, Ship Berthing, Cargo Working | 절차 안내 또는 업무 기능 (로그인 여부 미확인) |
| 실적·선박 | Performance Record, Performance Summary, Ship Particulars | 데이터·등록 기능 추정 |
| 커뮤니티 | Community, Notice, MSDS, Site Link | 정보 |
| 운영 현황 | 메인 Berthing Plan 위젯 | 접안 계획 공개 여부·범위 미확인 |

- 해석 [추론]: **공개 정보 포털 + 회원제 업무 포털**이 섞인 구조. Ship Vetting·Ship Particulars·Berthing Plan이 단순 안내 페이지인지 실제 등록·조회 기능인지, 실적 데이터가 선박별인지 집계인지는 공개 자료로 확인 불가 → §7에서 반드시 확인.
- Mooring Facilities 등 일부 페이지는 robots.txt로 자동 수집이 막혀 있음 → **크롤러 금지**. 사람이 직접 읽고 정리하거나 원문을 멘토에게 요청.

### 1-3. 공개 페이지에서 확인된 운영 규칙 (= 에이전트 룰 엔진의 재료)

**울산CLX (Entry Guide)**
- 입출항 보고: 울산 PTMS(VHF Ch.14) — 입항예정(항계 도착 1~2시간 전), 항계 진입, 도착, 이동, 출항 보고의 시점·항목이 정의되어 있음
- 도선: E-1~E-3 묘박지를 제외하고 접·이안·투묘·양묘 시 강제 도선. VLCC는 별도 승선 지점. 항계 도착 2시간 전 울산파일럿(Ch.13/16) 호출
- 접·이안 시간 제한
  - SK 1~2번 부두: 아스팔트·윤활유·유황 선적선 외에는 주간에만 접·이안
  - SK 3~8번(돌핀): 공선 30,000GT 미만·적재 25,000GT 미만 선박 외에는 **접안은 주간만**, 이안은 24시간
  - SK 부이(SBM): **야간 계류 불가**, 이안은 주야간 가능
- 청수: 묘박지에서 부선 공급 가능, SK 해상터미널에서는 부선 공급 금지
- 연료유(벙커): 묘박지 부선 공급 가능, SK 6·7·8번 부두는 송유관 공급 가능, 터미널 내 부선 공급 금지

**인천CLX (Entry Guide)**
- 인천 VTS 보고 절차, VHF Ch.65A(SKIPC 접·이안), Ch.71(대기)
- 접안 야간 제한 22:00~04:00
- 터미널에서 청수·선용품·벙커 공급과 폐기물 처리 불가

**SK Terminal Safety Regulation (인천판 국/영문 PDF)**
- 하역 안전은 선장과 터미널 대표의 공동 책임. 하역 전·중 터미널이 Ship/Shore Safety Check List 기준으로 점검하고, 미충족 시 하역 불가·중지, 반복 위반 시 이안 조치 가능
- 하역 통신 VHF Ch.71, 초기 유속 1 m/s 이하, 방출 시 매니폴드 압력 7.5 kg/cm² 이하, IG 탱크 산소 8% 이하, 정전기 관련 30분 규칙 등 수치 규정
- **풍속 한계 수치는 체크리스트 remark에 기재된다고만 되어 있고 본문에 수치 없음** → 현업 확인 대상
- 계류줄 최소 개수(DWT 구간별), 대조기 조차 약 9.8 m·조류 최대 약 3노트(인천), 유출 시 정화비용 선주 부담 등
- 울산판 PDF도 같은 경로에 있을 가능성 [추론] → 사이트에서 직접 확인

### 1-4. 울산 SK 선석 제원 (울산항만공사 공개 표, 기준일 미표기 — 최신값은 현업 확인)
| 선석 | 최대 DWT | 선석 수 | 길이(m) | 형식 | 수심(m) | 주요 화물 |
|---|---|---|---|---|---|---|
| SK1 Pier | 5,000×2 | 2 | 260 | 중력식 | 7.5 | Oil |
| SK2 Pier | 5,000 | 1 | 150 | 중력식 | 7.5 | Oil |
| SK2 Pier (별도 행) | 3,000×2 / 4,000 / 6,000 | 4 | 430 | Landing pier | 8 | Oil |
| SK3 Pier | 50,000 | 1 | 130 | Dolphin | 12 | Oil, Chemicals |
| SK4 Pier | 10,000 / 4,000×2 | 3 | 228 | Dolphin | 10 | Oil |
| SK5 Pier | 2,000×2 / 4,000 / 5,000 / 15,000 | 5 | 798 | Dolphin | 7–11 | Oil |
| SK6 Pier | 70,000 | 1 | 347 | Dolphin | 15 | LPG, Oil |
| SK7 Pier | 130,000 | 1 | 370 | Dolphin | 15 | Oil, Chemicals |
| SK8 Pier | 150,000 | 1 | 400 | Dolphin | 18 | Crude, Oil |
| SK2 Buoy | 325,000 | 1 | – | SBM | 27 | Crude |
| SK3 Buoy | 325,000 | 1 | – | SBM | 27 | Crude |

(참고: SK가스 Gas Pier 1,000/5,000/8,500 DWT, 3선석, LPG)

### 1-5. 회사 맥락 [사실]
- 울산CLX는 하루 84만 배럴을 처리하는 국내 최대 원유 처리시설이고 자체 부두 8곳을 갖고 있다. SK이노베이션은 매출의 약 70%를 수출에서 올린다(딜사이트 보도). → **부두 = 매출의 관문**
- 2026년 9월 SK이노베이션은 울산CLX의 '듀얼 브레인'을 공개: AI가 24시간 데이터를 분석해 이상 징후·대응안을 제시하고 엔지니어가 최종 결정하는 Human-in-the-loop 방식. 2030년까지 연 1,000억원 효과가 목표. 최태원 회장이 같은 달 울산CLX 구성원의 '1인 1에이전트' 활용 현황을 점검.
- 보도된 듀얼 브레인 적용 영역은 공정 최적화·예지정비·안전환경(SHE) 중심 → **해상터미널(입·출하) 영역은 상대적으로 비어 있음** [추론]

---

## 2. 업무 흐름으로 다시 보기

| 단계 | 주요 행위자 | 핵심 업무 | 대응 SEAGATE 메뉴 |
|---|---|---|---|
| ① 노미네이션·입항 전 | 용선주·대리점 ↔ 터미널 | 선박 제원 제출(Q88 등), 선석 적합성·Vetting 심사, ETA·접안 시간 조율 | Ship Particulars, Ship Vetting, Mooring Facilities |
| ② 입항·접안 | 선장·도선사·PTMS·터미널 | 보고 절차, 강제 도선, 주간/야간 접안 제한, 조석·기상 | Entry Guide, Berthing Plan |
| ③ 하역 | 당직사관 ↔ 터미널 | Ship/Shore Safety Check List, 유속·압력·IG 관리, 기상 한계 시 중단 | SK Terminal(안전규정), MSDS |
| ④ 출항·사후 | 터미널·용선주 | 하역 실적, 지연 원인, 체선(대기) 비용 정산 | Cargo Working(Performance) |

**Pain point 가설 [추론 — §7 인터뷰로 검증하기 전까지 '가설'로만 사용]**
1. 정보가 정적 페이지·PDF로 흩어져 있음(울산/인천 × 국/영문) → 외국 선장·대리점의 반복 문의(전화·메일·VHF)
2. 입항 전 검토(제원 vs 선석 한계, 야간 접안 규칙, 서류 누락, Vetting)가 문서 대조 중심 수작업 → 건당 시간 소요·누락 위험
3. ETA 변경·기상 악화 시 접안계획 재조정과 다수 이해관계자(대리점·도선·예선·출하) 통보가 연쇄 발생
4. 대기 시간 = 체선료 → 2026년 시장에서 특히 비쌈

---

## 3. 왜 지금 이 방향이 먹히는가

- **회사 언어와 일치 [사실 기반]**: '듀얼 브레인'(AI는 분석·제안, 사람은 결정)과 '1인 1에이전트'. → 우리 메시지: **"듀얼 브레인을 공장에서 부두까지"**
- **비용 근거 [사실]**: 2026년 9월 중동–아시아 VLCC 용선료가 하루 120만 달러로 사상 최고(FT 인용 보도, 전년에는 대체로 하루 2만~5만 달러). 서방 제재 대상 유조선 900척 이상(로이터, 2025.12). OCIMF의 개편 검사제도 SIRE 2.0은 2024년 하반기부터 전면 시행. → 대기 1시간·Vetting 실수 1건의 비용이 큰 시기
- **SKALA 우승작 패턴 [사실 + 추론]**
  - 1기: 실시간 번역 + 자동 회의록 화상회의 솔루션
  - 2기: Outlook 캘린더·프로젝트 문서 연동 맞춤 시나리오, AI 아바타 1:1 회화, 실시간 피드백
  - 공통점(추론): ① 심사위원이 즉시 공감하는 pain point ② 라이브로 돌아가는 데모 ③ 실제 업무 도구·데이터 연동. 평가 기준은 비공개.
  - 시사점 [추천]: 우리 주제는 도메인 특화라 설명 비용이 큼 → **"선박 한 척이 SK 부두에 붙기까지의 하루"**를 스토리로 데모해야 함

---

## 4. 후보 비교와 추천 [추천]

| 후보 | 핵심 기능 | 현업 가치 | 에이전트성* | 데이터 확보 | 데모 임팩트 | 기간 내 구현 | 차별성 |
|---|---|---|---|---|---|---|---|
| A. SEAGATE Q&A 챗봇 | 가이드·규정·MSDS RAG, 다국어 | 중 | 하 | 상(공개자료) | 중 | 상 | 하 |
| **B. Pre-Arrival Agent** | 노미네이션 검토 자동화 + 접안 시간창 + 회신 초안, HITL | **상** | **상** | 중(공공API+합성) | **상** | 중 | **상** |
| C. 접안계획 재조정 | ETA·기상 변화 시 다선박 재배정(최적화 솔버) | 상 | 상 | 하(실 스케줄 필요) | 상 | 하 | 상 |
| D. 기상 작업중단 모니터 | 부이·예보 기반 중단 위험 예측·알림 | 중 | 중 | 상(공공API) | 중 | 상 | 중 |
| E. 하역실적·체선 분석 | Text-to-SQL, 지연 원인 리포트 | 중 | 중 | 하(실적 데이터) | 하 | 중 | 중 |

\* 에이전트성: 다단계 계획, 도구 호출, 상태 관리, 사람 승인 루프가 있는지

**결론: B를 코어로, A는 '외부 사용자 입구'로 가볍게, D는 B의 '시간창 추천' 안에 흡수, C는 Stretch.**
- SEAGATE의 Ship Particulars → Ship Vetting → Berthing Plan → Port Info를 한 흐름으로 꿰어 "고객 시스템을 제대로 연구했다"가 드러남
- 다단계 판단 + 도구 호출 + 사람 승인 = AI Agent 캡스톤 취지에 정확히 부합 (RAG만 하는 팀과 차별)
- MCP 서버 경계가 자연스럽게 나와 MCP 요구사항을 억지 없이 충족
- 공공 API로 '진짜 데이터' 감을 주고, 비공개 내부 데이터는 합성으로 대체 가능

한 줄 피치(초안): **"선박 한 척이 SK 부두에 붙기까지 필요한 검토를 AI가 근거와 함께 미리 끝내고, 담당자는 승인만 한다."**
이름 후보: SEAGATE Pre-Arrival Agent / Sea Brain(듀얼 브레인 연상)

---

## 5. 추천안 상세 — SEAGATE Pre-Arrival Agent

### 5-1. 사용자
- 외부: 선박대리점·선장 — 노미네이션 제출, 진행 상태 확인, 규정 질의
- 내부: 터미널 담당자(Vetting·접안계획) — 검토 보고서 확인, 승인·반려·수정

### 5-2. 데모 시나리오 (전부 가상 데이터, 발표 시 '가상' 명시)
1. 대리점이 VLCC 노미네이션 제출: 원유, ETA 새벽 02:30, 희망 SK2 Buoy, Q88(PDF) 첨부
2. **Intake**: Q88 파싱 → DWT·LOA·흘수·매니폴드 등 구조화, 누락 항목 표시
3. **Compatibility**: 선석 제원 대비 적합(SBM 325,000 DWT·수심 27m) / 그러나 **SBM 야간 계류 불가 규칙 → 02:30 접안 불가** 판정
4. **Window**: 일출·박명(KASI) + 조석(KHOA) + 풍속·파고(KMA) → "익일 오전 계류 권장 시간창" 제안. 임계치는 화면에 '설정값(가정)'으로 표시
5. **Vetting**: 합성 레지스트리 기준 최근 검사 경과·선령 등 규칙 체크 + 공개 제재 리스트 유사명 매칭 → "담당자 확인 필요" 플래그 (자동 거절 X)
6. **Report/Comms**: 판정마다 근거(룰 ID·출처 문서·API 조회 시각) 첨부 + 대리점 영문 회신·서류 요청 메일 초안
7. **HITL**: 담당자가 수정·승인 → Berthing Plan 초안 반영 → 대리점에 상태 알림
8. (옵션) 선장 질문 "SK8에서 벙커 받을 수 있나?" → Entry Guide 근거로 "송유관 공급 가능, 부선 공급 금지" + 출처 표시

### 5-3. 에이전트 구성 (LangGraph 예시)
```
Supervisor
  → Intake(문서 파싱)
  → [Compatibility ∥ Vetting ∥ Window]   (병렬)
  → Reviewer(자기검증: 근거 없는 판정 제거, 판정 간 충돌 확인)
  → Report/Comms(보고서·메일 초안)
  → interrupt(사람 승인)   ← Human-in-the-loop
  → Commit(승인된 결과만 DB 반영)
```
- 원칙: **숫자 비교·시간 규칙 판정은 결정론적 코드(룰 엔진)**, LLM은 문서 이해·설명·초안·애매한 케이스 질의만 담당. LLM에게 DWT 비교를 맡기지 않는다.
- 룰은 데이터로 관리: `rule_id / terminal / berth / 조건 / 효과 / 출처(URL·페이지) / 확인상태(공개자료|가정|현업확인)` → 모든 판정에 출처가 자동으로 붙음
  - 예: `ULS-SBM-NIGHT`(SBM 야간 계류 불가, Entry Guide 울산), `ULS-SK38-DAYTIME`(SK3~8 대형선 주간 접안), `ULS-DWT-MAX`(선석 최대 DWT), `ULS-DRAFT-UKC`(흘수 + 여유수심 ≤ 수심, **UKC 값은 가정 → 현업 확인**)
  - '주간'의 정의(일출~일몰인지, 고정 시각인지)도 가정 → 현업 확인

### 5-4. MCP 서버 설계
| MCP 서버 | 구현(제안) | 주요 tools | 데이터 |
|---|---|---|---|
| `seagate-terminal` | Spring Boot + Spring AI MCP Server | `list_berths`, `get_berth_spec`, `check_berth_rules`, `get_berthing_plan`, `get_nomination`, `propose_slot`(초안만) | PostgreSQL: 선석·룰·노미네이션·계획 |
| `terminal-kb` | Python FastMCP | `search_regulations`, `get_section`(출처 반환) | Entry Guide·안전규정 PDF·MSDS (pgvector) |
| `ocean-data` | Python FastMCP | `get_tide_forecast`, `get_marine_obs`, `get_sun_times` | KHOA·KMA·KASI Open API (+캐시) |
| `vessel-intel` | Python FastMCP | `lookup_vessel`, `get_inspection_history`, `screen_sanctions` | 합성 레지스트리 + 공개 제재 리스트(예: 미국 OFAC SDN) |
| `comms` | Python 또는 Java | `draft_email`, `notify`(승인 후 발송) | – |

- **MCP를 쓰는 이유(발표용)**: 도구 경계·권한을 분리하고, 같은 MCP 서버를 터미널 담당자 개인 에이전트('1인 1에이전트')나 다른 사내 에이전트가 재사용할 수 있음 → "결과물이 앱 하나가 아니라 재사용 가능한 사내 자산"
- 거버넌스: write 계열 tool은 **초안 생성만** 허용, 확정은 UI 승인 API로만 / 모든 tool 호출 감사 로그 / 외부 사용자 Q&A에는 읽기 전용 tool만 노출

### 5-5. 아키텍처
```
[SEAGATE형 포털(외부: 대리점·선장)]   [검토 콘솔(내부: 터미널 담당자)]
              │ REST                         │ REST / WebSocket
              ▼                              ▼
      [Spring Boot API: 도메인·인증·승인·감사로그] ── PostgreSQL (+pgvector)
              │ 이벤트(노미네이션 생성)        ▲ MCP(seagate-terminal)
              ▼                              │
      [Agent Service: Python + LangGraph] ── MCP ── terminal-kb / ocean-data / vessel-intel / comms
              │
      [LLM API(과정 제공)] + [트레이싱: Langfuse 등]
```
- 배포: Docker Compose로 시작. 커리큘럼에 Cloud Native 비중이 크면 K8s 배포를 가산점용으로.

### 5-6. 데이터 전략
| 구분 | 데이터 | 확보 방법 |
|---|---|---|
| 공개(실데이터) | SEAGATE 공개 페이지·안전규정 PDF, 울산항만공사 선석 제원, KHOA 조석예보, KMA 해양기상관측(부이·파고부이), KASI 출몰시각(일출·항해박명), 해수부 항만별 선박입출항실적, KOSHA MSDS | 공식 Open API + 수동 수집(크롤링 금지) |
| 합성 | 선박 레지스트리, Q88 PDF, 노미네이션, 검사 이력, 접안계획 이력 | 공개 제원 분포 기반 생성기, 데이터에 '가상' 표기 |
| 요청 | 실제 Vetting 기준, 풍속·파고 작업 한계, UKC 기준, 비식별 접안계획·실적 샘플 | 멘토 경유 요청, 불가 시 가정값을 문서화 |

- API 승인: KHOA 조석예보·해수부 입출항실적은 개발계정 자동승인, **KMA 해양기상관측자료는 개발단계도 심의승인** → 먼저 신청

### 5-7. 평가 설계 (발표에서 숫자로 말하기)
- 테스트셋: 합성 노미네이션 30~50건 + 정답 라벨(제원 초과 / 흘수·수심 / 야간 ETA / 서류 누락 / 제재 유사명 / 정상)
- 지표: 문제 탐지 Recall·Precision, 판정별 근거 첨부율, 잘못된 근거 비율, 건당 검토 시간(팀원이 SEAGATE 페이지만 보고 검토 vs 에이전트 보조 — **직접 측정한 값만**), tool 호출 성공률·지연
- 현업 비용 절감액은 측정 불가 → "가정 기반 추정"으로 명확히 라벨

### 5-8. MVP vs Stretch
- **MVP**: 노미네이션 1건 end-to-end(Intake → Compatibility → Window → Vetting → Report → 승인) + Q&A-lite + 평가셋 결과
- **Stretch**: 다선박 일정 충돌 해결(OR-Tools CP-SAT 등), 기상 악화 시 재계획 제안, 메일·메신저 연동, 다국어 회신, 인천CLX 룰셋 추가

---

## 6. 진행 플랜 (기간 미확정 → 6주 가정, 실제 일정에 맞춰 조정)
| 주차 | 목표 | 산출물 |
|---|---|---|
| W1 | 문제 검증 | 현업 인터뷰, pain point 확정, 범위 동결, 데모 시나리오 1개 |
| W2 | 기반 | DB 스키마, 선석·룰 데이터 적재, API 키 발급, 합성 데이터 생성기, MCP 서버 뼈대 |
| W3 | 핵심 판정 | Compatibility·Window 룰 엔진 + MCP tool, Q88 파싱 |
| W4 | 에이전트 | LangGraph 오케스트레이션, Vetting, Report/Comms, HITL interrupt |
| W5 | UI·평가 | 포털·검토 콘솔, 테스트셋 평가, 트레이스 |
| W6 | 완성 | 리허설, 녹화 백업 데모, 발표자료 |

역할 예시(5인): PM·도메인 / BE(Spring Boot·DB·MCP 서버) / AI(LangGraph·프롬프트·평가) / Data(공공 API·합성 데이터·RAG) / FE(포털·콘솔)

---

## 7. 현업·멘토 인터뷰 질문
1. 노미네이션 접수부터 접안 확정까지 실제 절차·사용 시스템·양식은? 한 척당 검토 시간은?
2. Vetting 기준(선령, SIRE 2.0 검사 유효기간, PSC 이력, 제재 확인)은 누가 어떤 도구로 판단하나? 외부 서비스를 쓰나?
3. SEAGATE의 Ship Particulars / Ship Vetting / Berthing Plan은 로그인 후 실제로 어떤 기능이고, 얼마나 쓰이나?
4. 선장·대리점에게 가장 자주 받는 문의 Top 5와 채널(전화·메일·VHF)은?
5. 접안계획 변경 빈도와 주원인(ETA 변경·기상·탱크/생산 일정)은?
6. 기상 작업 중단 기준(풍속·파고·SBM 계류 한계)과 UKC 기준 수치를 공유받을 수 있나?
7. 대기(체선)로 인한 비용·분쟁이 실제 이슈인가? 어느 단계 지연이 가장 비싼가?
8. 제공 가능한 데이터(비식별 샘플) 범위와 보안상 금지사항은?
9. "이것만 있으면 내일부터 쓰겠다"는 기능 하나는?

## 8. 하지 말 것 / 리스크
- 사이트 내용을 담은 챗봇만 만들기 (차별성 낮음)
- 에이전트가 승인·접안 확정을 자동으로 하는 설계 (안전·책임 문제, 듀얼 브레인 취지와도 어긋남)
- 합성 데이터·가정값을 실데이터·실효과처럼 발표
- SEAGATE 자동 크롤링 (robots.txt 차단)
- MVP에 최적화 솔버·다중 터미널·다국어를 한꺼번에 넣는 범위 과욕

## 9. 미확정 사항 (사용자 확인 필요)
- 이 주제가 SKALA '현업 주제 풀'에서 배정된 과제인지, 팀 자율 선택인지 (공식 과제정의서 유무)
- 팀 인원, 프로젝트 기간·마감, 필수 요건(MCP 필수 범위, 제공 LLM·클라우드)
- 멘토가 SK이노베이션(해상터미널) 현업인지 SK AX 소속인지
- "여기에 사용될"의 의미: SEAGATE 외부 포털 기능 확장인지, 내부 담당자 도구인지 → 추천안은 둘 다 커버하되 내부 검토 도구가 코어

## 10. 출처
- SEAGATE 회사소개: https://skseagate.skinnovation.com/view/seagate/abo/company/company01
- SEAGATE Entry Guide – Ulsan CLX: https://skseagate.skinnovation.com/view/seagate/inf/entry/entry01
- SEAGATE Entry Guide – Incheon CLX: https://skseagate.skinnovation.com/view/seagate/inf/entry/entry02
- SK Terminal Safety Regulation (인천, 영문/국문): https://skseagate.skinnovation.com/static/skiaf/download/SK_Safety_Regulation_incheon_eng.pdf , https://skseagate.skinnovation.com/static/skiaf/download/SK_Safety_Regulation_incheon_kor.pdf
- 구 SEAGATE(메뉴 구조, 검색 스니펫): https://www.skseagate.com/Seagate_default.asp
- 울산항만공사 Liquid Bulk Cargo 선석 제원: https://www.upa.or.kr/eng/contents.do?mid=0203020000
- 울산CLX 듀얼 브레인·1인 1에이전트: https://news.mtn.co.kr/news-detail/2026091514285795364 , https://dealsite.co.kr/articles/169000 , https://www.dailian.co.kr/news/view/1689607 , https://www.mydaily.co.kr/page/view/2026090308481976653
- VLCC 용선료 사상 최고(SBS Biz, 2026-09-23): https://biz.sbs.co.kr/amp/article/20000336533
- 제재 대상 유조선 900척 이상(로이터, 2025-12-15): https://www-web.itiger.com/news/2591619370
- SIRE 2.0 시행 1주년(2025-09): https://airfreight.news/articles/full/sire-2.0-one-year-on-ocimf-marks-milestone-and-sets-course-for-the-future-of-vessel-inspections
- SKALA 우승 사례·프로젝트 진행 방식: https://www.2026skala.co.kr/
- 공공 API
  - KHOA 조석예보(시계열): https://www.data.go.kr/data/15156022/openapi.do
  - KMA 해양기상관측자료 조회서비스: https://www.data.go.kr/data/15043550/openapi.do
  - KASI 출몰시각 정보: https://www.data.go.kr/data/15012688/openapi.do
  - 해수부 항만별 선박입출항실적 통계: https://www.data.go.kr/data/15059059/openapi.do
  - KOSHA 물질안전보건자료 조회: https://www.data.go.kr/data/15157612/openapi.do
  - 울산항만공사 울산항 부두위치정보: https://www.data.go.kr/data/15155218/fileData.do
