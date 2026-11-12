# 요구사항 분석 문서 세트 — PRD · 시나리오 · 간트

- 작성일: 2026-11-04 · 버전: **v0 (초안, 팀 합의 전)**
- 용도: SKALA 최종 프로젝트(체선료 Agent)의 요구사항 분석 단계 산출물과, 그것을 쓰는 방법
- **주의 (2026-11-04)**: 과제 원문([`official-brief.md`](official-brief.md))을 받았다. `03` PRD v0의 코어 A/B·비목표(N-1·N-2)와 `06`·간트의 A 전용 줄은 원문과 어긋난다. 요구사항 분석은 [`07-requirements-analysis.md`](07-requirements-analysis.md)에 있고, 이 문서들은 그 결과로 고친다.
- 표기: [사실] / [추론] / [추천] / [가정] / [확인 필요] ([`../domain/00-README.md`](../domain/00-README.md) §3과 같다). 근거 등급은 CONFIRMED / DOC / VIRTUAL / HYPOTHESIS. **현업 확인(CONFIRMED)은 아직 0건**이다.

## 파일

| 파일 | 무엇 | 언제 읽나 |
|---|---|---|
| [`00-start-here.md`](00-start-here.md) | **처음이라면 이것만.** 간트·PRD가 뭔지, PRD 6칸 채우기, 간트 5단계와 시작용 표, 잘 만든 간트 체크리스트, 오늘 할 일 3가지 | 가장 먼저 |
| [`official-brief.md`](official-brief.md) | **과제 원문** (붙여 준 그대로, 고치지 않는다). 요구사항 분석의 근거 | 요구를 뽑을 때, 출처를 확인할 때 |
| [`07-requirements-analysis.md`](07-requirements-analysis.md) | **요구사항 분석 문서.** 원문에서 뽑은 해야 하는 일(R), 지켜야 하는 조건(C), 하지 않는 일(X), 모르는 것(Q)과 화면 대응, 이미 있는 것 | 요구사항을 볼 때 (가장 중요한 문서) |
| [`08-questions.md`](08-questions.md) | **질문 정리.** 07의 Q1~Q12를 누구에게 어떤 순서로 물을지 묶고, 우리 가정과 보낼 글(교수님, 현업 멘토)을 붙였다 | 질문을 보내거나 답을 적을 때 |
| [`09-first-steps.md`](09-first-steps.md) · `answers/` | **먼저 할 것 두 가지.** 원문 6절의 한 흐름 관통, 계산 규칙과 정답 세트를 풀이하고, 우리가 가진 정답(TC 7개)과 새 손계산 정답(SC-01)을 정리했다. `answers/`는 SC-01의 엔진 입력 파일 | 계산 규칙과 정답을 볼 때 |
| [`10-requirements-list.md`](10-requirements-list.md) | **요구사항 목록 (구글 문서 '프로젝트 정의·요구사항서' 3절용).** 기능 16개·비기능 9개(팀원 추가 포함, FR-02는 02-1~3으로 나눔)를 ID·우선순위·수용기준으로 정리하고, 팀 캔버스 어느 줄에서 왔는지 근거를 붙였다 | 요구사항서를 채우거나 고칠 때 |
| [`11-requirements-extraction.md`](11-requirements-extraction.md) | **요구사항 전수 추출 (후보 목록).** 구글 문서 탭 2(기능 33·비기능 12)와 탭 3 리뷰를 기준으로 기능 78개(FR-18~95)·비기능 72개(NFR-13~84)를 새로 뽑고, 범위 밖·제안 숫자·탭 3 겹침·추가 질문(Q-22~)을 붙였다. 표 열이 문서 탭 2와 같아 그대로 붙여 넣을 수 있다 | 요구사항을 더 채울 때, 팀에 후보를 보일 때 |
| [`12-usecase-diagram.md`](12-usecase-diagram.md) · `usecase/` | **유스케이스 다이어그램.** 요구사항서 실시간 탭(FR 60 · NFR 22) 기준으로 액터 7 · 유스케이스 18을 뽑아 그렸다. 그리는 규칙, 선이 겹치지 않게 놓는 법, 액터 · 유스케이스 표, 확인한 참고 자료. 그림은 `usecase/make_usecase_diagram.py`가 만든다 | 그림을 보거나 고칠 때, 그리는 법을 볼 때 |
| [`13-usecase-scenarios.md`](13-usecase-scenarios.md) | **유스케이스 시나리오 18개.** 유스케이스마다 액터, 사전조건, 기본 흐름, 대안 · 예외, 확인 방법을 FR · NFR 번호와 함께 적었다. NFR이 걸리는 곳 표와 팀에 확인할 것 7개 | 화면 흐름이나 테스트 순서를 정할 때 |
| [`14-functional-spec.md`](14-functional-spec.md) · `funcspec/` | **기능명세서.** 요구사항 60개를 기능 60개(그룹 10개)로 풀어 기능마다 입력 → 처리 → 출력, 다른 길·멈춤, 완료 기준을 적었다. 업무 단계 흐름, 계산 한 번의 안쪽, 비기능 22개가 걸리는 곳, 확인할 것 9개, 용어 포함. 내용은 `funcspec/spec_data.py`, 글과 피그마 보드 원본(`funcspec-board.html`)은 `funcspec/make_funcspec.py`가 만든다 | 기능을 구현하거나 테스트를 짤 때, 흐름을 볼 때 |
| [`15-hidden-nfr-ux-500.md`](15-hidden-nfr-ux-500.md) · `hidden500/` | **숨은 비기능 요구 250 + 페인 포인트 기반 화면 특징 250 (2026-11-11, 제안).** 요구사항서 실시간 탭(NFR 22개)에 없거나 약한 비기능 요구와, 과제 원문·멘토링 자료의 페인 포인트 12개에서 나온 화면 특징을 항목마다 이유·수용기준·우선순위·관련 번호와 함께 적었다. 먼저 볼 20개, CSV(`hidden500/hidden500.csv`), 그림 7장(500개 지도 · 페인별 개수 · 먼저 볼 20개 · 화면 목업 4장). 원본은 `hidden500/items_*.txt`, 생성은 `hidden500/make_hidden500.py --png`와 `hidden500/make_mockups.py` | 요구사항을 보강하거나 화면을 기획할 때 |
| [`15-hidden-requirements.md`](15-hidden-requirements.md) · `hidden/` · `ux/` | **드러나지 않은 요구 후보 502개.** 실시간 탭(FR 60 · NFR 22)에 없는 비기능 요구 366개(갈래 24개)와 페인 포인트에서 나온 UI/UX 특징 136개(갈래 9개)를 이유 · 확인 방법 · 우선순위 · 때(지금 / 시연 / 도입)와 함께 적었다. 화면 그림 7장은 `ux/`에 있다. 내용은 `hidden/items/*.txt`, 그림은 `ux/make_screens.py`가 만든다 | 요구를 더 채울 때, 화면을 기획할 때, 발표 질문에 대비할 때 |
| [`../milp/milp-final.md`](../milp/milp-final.md) · `../milp/` | **수리계획법 최종본 (2026-11-11).** 작업계획 선택 MILP — 솔버에 넣는 식 (1)~(8), 풀기 전에 쓰는 생성 규칙 식 (9)~(20), 기호표, 입력 컬럼이 들어가는 식, 검산 예제(1안 A1 + B3 $15,750). 피그마 '수리계획법' 페이지의 판 9개와 같은 내용이고 `make_milp_board.py`로 다시 만든다 | 식을 구현하거나 팀에 설명할 때 |
| [`wireframe.html`](wireframe.html) | **와이어프레임 세 장** (스케줄 비교, 보고서 초안, 검증 결과). 브라우저로 연다 | 화면과 요구의 대응을 볼 때 |
| [`01-prd-guide.md`](01-prd-guide.md) | PRD가 무엇이고 어떻게 쓰는 게 맞는지. 원칙 8개, 섹션별 작성법, 요구 문장 쓰는 법(EARS), MoSCoW, 추적성, AI Agent 제품의 추가 항목, 자기 점검표 | PRD를 처음 쓰거나 리뷰할 때 |
| [`02-requirements-analysis-workplan.md`](02-requirements-analysis-workplan.md) | 요구사항 분석 단계의 작업 12개, 시나리오 작성법, 도출·우선순위·검증 방법, **지금 우리가 할 일** | 이번 주에 무엇을 할지 정할 때 |
| [`03-prd-v0.md`](03-prd-v0.md) | 체선료 Agent PRD 초안. 코어(A/B) 선택 규칙, 요구사항 34개와 현황, 성공 기준, 위험, 결정 로그 6건, 추적 매트릭스 | 팀 리뷰, 멘토에게 보일 때 |
| [`04-scenarios.md`](04-scenarios.md) | 시나리오 명세 8개(청구 검증 3, 노출 설명 2, 공통·예외 3), AS-IS/TO-BE 흐름도, 시나리오-요구 커버리지 | 요구를 확인하거나 평가셋을 만들 때 |
| [`gantt/starter.md`](gantt/starter.md) · `gantt/starter.csv` | **시작용 간트 표 (우리 팀 값, 16행).** 날짜·선행·담당 역할이 채워져 있다. CSV는 시트로 가져갈 때 | 처음 일정을 볼 때, 팀에 일을 나눌 때 |
| [`gantt/gantt.md`](gantt/gantt.md) | 일정 v0. Mermaid 간트, 게이트, 작업 표 | 일정을 읽을 때 |
| [`gantt/gantt.html`](gantt/gantt.html) | **상호작용 간트 차트.** 브라우저로 연다 (시작용 16개/전체 34개 보기, 분기 A/B 보기, 의존선, 호버 상세, 인쇄) | 일정을 보고 말할 때 |
| `gantt/tasks.csv` · `gantt/gantt.config.json` | 간트의 **원본**. 날짜는 남은 기간 대비 비율 또는 확정 날짜 | 일정을 고칠 때 |
| `gantt/make_gantt.py` | 원본에서 HTML·Markdown·날짜 CSV·시작용 표를 만들고 검사하는 생성기 (표준 라이브러리만) | `python3 docs/requirements/gantt/make_gantt.py` |
| `gantt/tasks.resolved.csv` | 날짜가 풀린 사본(UTF-8 BOM). Excel·Google Sheets·Notion으로 가져갈 때 | 다른 도구로 옮길 때 |
| [`05-references.md`](05-references.md) | 확인된 외부 링크: 잘 만든 PRD, 요구사항 작성법, 간트 차트 | 예시를 보고 싶을 때 |
| [`06-prd-6cells.md`](06-prd-6cells.md) | **우리 팀의 PRD 6칸 (v0).** 00의 6칸을 채운 한 장과 정해진 방식(선택·기본값·모름) | 팀에 공유할 때, PRD 본문의 뼈대를 볼 때 |

## 읽는 순서

- **처음이라 감이 안 올 때**: `00-start-here.md` 한 장만 읽고 시작한다. 우리 팀이 채운 6칸은 `06-prd-6cells.md`, 나머지는 막힐 때 찾아본다
- **팀원**: 이 README → `official-brief.md` → `07` → `wireframe.html` → `gantt/gantt.html` (`03`·`04`·`06`은 원문 기준으로 고치기 전이라 참고만)
- **멘토에게 보일 때**: `07` §1·§6 (한 장 요약, 물어볼 것)과 `wireframe.html`
- **방법을 알고 싶을 때**: `01` → `02` → `05`
- **새 Claude 세션**: 이 README → `07` → `official-brief.md` → `gantt/tasks.csv`

## 지금 막혀 있는 입력

이 값들이 없어서 문서의 해당 부분은 [확인 필요]이거나 [가정]이다. (2026-11-04 과제 원문을 받아 코어 A/B 질문은 사라졌다. 지금 물을 것은 [`07`](07-requirements-analysis.md) 6절의 Q1~Q12이고, 보낼 글은 [`08`](08-questions.md)에 있다.)

| 입력 | 영향 | 질문 |
|---|---|---|
| 마감일(중간 점검·최종 발표·제출) | 간트의 모든 날짜 | D-04, 질문지 Q6 |
| 팀 역할 분담·주당 가용 시간 (인원은 5~6명으로 확인, 2026-11-04) | 간트의 담당 이름, 병렬 가능 여부 | D-04 |
| 평가 기준 (과제 원문은 [`official-brief.md`](official-brief.md)로 받았고, 평가 기준은 원문에 없다) | 성공 기준, 에이전트 구성(D-06) | 질문지 Q6 |
| 멘토 답(Q1~Q6) | 코어 목표(D-01), 비목표(D-02), 숫자 주장(D-03) | 질문지 |
| 비식별 샘플(SOF·NOR·청구서·코드표) | INT-03, 평가셋 현실성 | 질문지 Q5 |

## 갱신 규칙

1. **원본은 한 곳.** PRD·시나리오는 이 폴더의 md, 일정은 `tasks.csv`와 `gantt.config.json`이다. `gantt.html`·`gantt.md`·`tasks.resolved.csv`·`starter.md`·`starter.csv`는 생성물이므로 직접 고치지 않는다.
2. **버전은 게이트에 묶는다.** v0(지금) → v1(G1: 코어 확정) → v2(F: 범위 동결). 바뀔 때마다 `03` §12 변경 이력에 적는다.
3. **새 정보가 들어오면 이 순서로 고친다**: `03` §11 결정 로그 → §6 요구(우선순위·근거 등급·현황) → `04` 시나리오 → `tasks.csv` → `make_gantt.py` 실행.
4. **현황 열은 코드·테스트로 확인한 것만** 적는다. 확인하지 않았으면 △ 또는 "확인 필요"로 둔다.
5. 정의서·진단·인터뷰 질문지(Claude Doc)와 값이 어긋나면 이 폴더와 Doc을 같이 고친다.

## 간트 미리보기

- 파일을 직접 연다: `docs/requirements/gantt/gantt.html`
- 앱의 미리보기: `.claude/launch.json`의 `requirements-preview`(포트 8766, `docs/requirements`)를 시작하고 `/gantt/gantt.html`로 간다.
