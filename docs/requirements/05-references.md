# 링크 레퍼런스 — PRD, 요구사항 분석, 간트

- 확인일: 2026-11-04. 확인 방법: 아래 링크를 실제로 열어 응답(HTTP 200)과 페이지 제목을 확인했다.
- 설명은 페이지 제목과 검색 결과 요약, 열람한 범위에서 쓴 것이다. 외부 자료의 내용이 맞는지는 직접 읽고 판단한다.
- 상업 서비스 블로그는 자사 도구 홍보가 섞여 있다. 표준·원저자 자료를 먼저 보고, 블로그는 템플릿과 예시를 비교하는 용도로 쓴다.
- 이 폴더의 문서와 연결: 원칙 [`01-prd-guide.md`](01-prd-guide.md), 작업 [`02-requirements-analysis-workplan.md`](02-requirements-analysis-workplan.md), PRD [`03-prd-v0.md`](03-prd-v0.md).

---

## 1. 잘 만든 PRD — 가이드·템플릿·완성 예시

| 자료 | 무엇이 있나 | 볼 이유 |
|---|---|---|
| [Atlassian — What is a PRD?](https://www.atlassian.com/agile/product-management/requirements) | PRD의 개념과 작성 안내. Atlassian은 PRD를 Confluence 템플릿으로 쓴다고 밝힌다 | 가장 널리 인용되는 입문. 페이지 존재와 제목은 확인했고 본문 요약은 하지 못했다 |
| [Atlassian — PRD template (Confluence)](https://www.atlassian.com/software/confluence/templates/product-requirements) | 바로 복사해 쓰는 PRD 템플릿 | 섹션 구성의 기준선으로 삼기 좋다 |
| [Reforge — PRD: What Is It & How To Write It (7 templates)](https://www.reforge.com/blog/product-requirement-document-prd-templates) | 템플릿 7종과 완성 예시(노트 앱의 오프라인 지원) | 템플릿마다 어떤 팀에 맞는지 비교할 수 있다 |
| [Attract Group — PRD template, example, writing guide](https://attractgroup.com/blog/product-requirements-document/) | 완성된 예시(SaaS 구독 일시정지 기능)와 작성 가이드 | 플레이스홀더가 아니라 결정이 적힌 예시를 볼 수 있다 |
| [Inflectra — Free PRD template & example](https://inflectra.com/Ideas/Topic/PRD-Template.aspx) | 가상의 헬스케어 제품으로 채운 템플릿 | 요구사항 표를 어떻게 채우는지 본다 |
| [Aha! — PRD templates: what to include](https://www.aha.io/roadmapping/guide/requirements-management/what-is-a-good-product-requirements-document-template) | 템플릿에 들어갈 항목 해설 | 우리 §5 표준 구성과 대조해 빠진 것을 찾는다 |
| [ProductPlan — PRD (glossary)](https://www.productplan.com/glossary/product-requirements-document/) | 짧은 정의 | 팀원에게 한 화면으로 설명할 때 |
| [Product Marketing Alliance — PRD template (PDF)](https://www.productmarketingalliance.com/content/files/2024/09/Product-requirements-document-template.pdf) | 빈 양식 PDF | 인쇄·종이 리뷰용 |
| [Uvik — AI PRD template: fields, tests, worked example](https://uvik.net/blog/ai-prd-template/) | 실패 모드, 대체 동작, 사람 개입, 가드레일, 요구와 테스트의 연결 | AI Agent 제품 PRD의 추가 항목(`01` §9)을 점검한다 |
| [Amazon Working Backwards — PR/FAQ](https://workingbackwards.com/concepts/working-backwards-pr-faq-process/) | 가상의 보도자료와 FAQ를 먼저 쓰는 방식 | PRD와 다른 접근. 발표 스토리라인을 잡을 때 참고 |
| [PPSS — 구글 프로덕트 매니저가 알려주는 기획서 작성 꿀팁](https://ppss.kr/archives/226689) (한국어) | 기획서 작성 요령 | 한국어 실무 감각. PRD 전용 자료는 아니다 |

## 2. 요구사항 분석과 명세 작성

| 자료 | 무엇이 있나 | 우리 문서와의 연결 |
|---|---|---|
| [EARS — Alistair Mavin 공식 안내](https://alistairmavin.com/ears/) | 요구 문장의 다섯 패턴(상시·When·While·If-then·Where)과 복합 패턴 | `01` §6-2. 요구사항 문장을 쓰는 틀 |
| [EARS (Wikipedia)](https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax) | EARS의 배경 | 보조 |
| [ISO/IEC/IEEE 29148:2018 (IEEE Xplore)](https://ieeexplore.ieee.org/document/8559686) | 요구공학 프로세스와 좋은 요구의 속성을 다루는 표준의 소개 페이지 | `01` §6-4. 표준 본문은 유료라 개요만 볼 수 있다 [확인 필요: 속성 목록은 원문 대조 전] |
| [Volere — Requirements Specification Template](https://www.volere.org/templates/volere-requirements-specification-template/) | 요구사항 명세 템플릿 | PRD §6 요구사항 표를 더 정밀하게 만들 때 |
| [Software requirements specification (Wikipedia)](https://en.wikipedia.org/wiki/Software_requirements_specification) | SRS의 정의와 구성 | PRD와 SRS의 관계 (`01` §3) |
| [Requirements traceability (Wikipedia)](https://en.wikipedia.org/wiki/Requirements_traceability) | 요구 추적성과 추적표 | `03` §12 추적 매트릭스 |
| [Use case (Wikipedia)](https://en.wikipedia.org/wiki/Use_case) | 유스케이스와 시나리오의 개념 | `04` 시나리오 명세 양식 |
| [Mountain Goat — User stories](https://www.mountaingoatsoftware.com/agile/user-stories) | 사용자 스토리 작성법 | `01` §6-1 |
| [Atlassian — User stories with examples and a template](https://www.atlassian.com/agile/project-management/user-stories) | 사용자 스토리 예시와 템플릿 | 같음 |
| [Martin Fowler — Given When Then](https://martinfowler.com/bliki/GivenWhenThen.html) | 인수 기준을 쓰는 틀 | 인수 기준 열 |
| [Agile Business Consortium — What is MoSCoW prioritization?](https://www.agilebusiness.org/resource/what-is-moscow-prioritization/) | MoSCoW의 원 출처 단체의 설명 | `01` §7-1 |
| [MoSCoW method (Wikipedia)](https://en.wikipedia.org/wiki/MoSCoW_method) | MoSCoW 개요 | 보조 |
| [NN/g — Personas make users memorable](https://www.nngroup.com/articles/persona/) | 페르소나의 쓰임 | 사용자 정의 (`03` §2) |
| [Design Docs at Google](https://www.industrialempathy.com/posts/design-docs-at-google/) | 요구사항 다음 단계인 설계 문서 | 설계 단계로 넘어갈 때 |
| [요구공학 (위키백과)](https://ko.wikipedia.org/wiki/%EC%9A%94%EA%B5%AC_%EA%B3%B5%ED%95%99) (한국어) | 요구공학 개요 | 한국어 용어 확인 |
| [요구사항 분석 (위키백과)](https://ko.wikipedia.org/wiki/%EC%9A%94%EA%B5%AC%EC%82%AC%ED%95%AD_%EB%B6%84%EC%84%9D) (한국어) | 요구사항 분석 개요 | 한국어 용어 확인 |

## 3. 잘 만든 간트 차트 — 예시·템플릿·도구

| 자료 | 무엇이 있나 | 볼 이유 |
|---|---|---|
| [TeamGantt — 12 Gantt chart examples](https://www.teamgantt.com/resources/articles/gantt-chart-examples) | 프로젝트 유형별 예시 12개(애자일 소프트웨어 프로젝트 포함) | 막대·마일스톤·묶음을 어떻게 배치하는지 본다 |
| [Instagantt — Gantt chart examples](https://www.instagantt.com/templates) | 소프트웨어 스프린트, 제품 로드맵 등 무료 예시 | 템플릿을 그대로 복사해 시작할 수 있다 |
| [Miro — Agile project Gantt chart template](https://miro.com/templates/agile-project-gantt-chart/) | 애자일 프로젝트용 템플릿 | 팀 화이트보드에서 같이 편집 |
| [ClickUp — Software development project Gantt chart template](https://clickup.com/templates/gantt-chart/software-development-project) | 소프트웨어 개발 프로젝트용 템플릿 | 단계·의존성 구성 예시 |
| [Atlassian — What is a Gantt chart?](https://www.atlassian.com/agile/project-management/gantt-chart) | 간트 차트의 구성 요소와 무료 템플릿 | 개념 입문 |
| [Asana — What is a Gantt chart?](https://asana.com/resources/gantt-chart-basics) | 개념과 작성 순서 | 입문 |
| [ProjectManager — Gantt chart guide](https://www.projectmanager.com/guides/gantt-chart) | 정의, 예시, 사용법 | 의존성·임계 경로 설명 |
| [Microsoft — Gantt chart templates (Excel)](https://create.microsoft.com/en-us/templates/gantt-charts) | Excel 간트 템플릿 | 엑셀로 가볍게 관리할 때 |
| [Gantt chart (Wikipedia)](https://en.wikipedia.org/wiki/Gantt_chart) · [간트 차트 (위키백과)](https://ko.wikipedia.org/wiki/%EA%B0%84%ED%8A%B8_%EC%B0%A8%ED%8A%B8) | 역사와 개념 | 용어 확인 |
| [Mermaid — Gantt diagrams](https://mermaid.js.org/syntax/gantt.html) | 텍스트로 간트를 그리는 문법 | 우리 `gantt/gantt.md`가 이 문법을 쓴다 |
| [Mermaid Live Editor](https://mermaid.live/) | Mermaid를 붙여 넣어 바로 그림으로 보는 편집기 | `gantt.md`의 블록을 확인할 때 |
| [GanttProject](https://www.ganttproject.biz/) | 무료 데스크톱 간트 도구 | 시작·종료일을 드래그로 조정하고 싶을 때 |
| [Frappe Gantt](https://frappe.io/gantt) | 웹에 넣을 수 있는 오픈소스 간트 라이브러리 | 웹 화면에 간트를 넣게 될 때 |
| [이랜서 — 간트 차트란? 작성 방법과 활용법](https://www.elancer.co.kr/blog/detail/1157) (한국어) | 간트 차트 개념과 작성 방법 | 한국어 입문 |
| [ClickUp — 간트 차트 작성 방법](https://clickup.com/ko/blog/7183/how-to-create-a-gantt-chart) (한국어) | 단계별 작성 가이드 | 한국어 입문 |
| [Miro — 간트 차트 템플릿](https://miro.com/ko/templates/gantt-chart-templates/) (한국어) | 용도별 템플릿 | 한국어 화면 |

## 4. 우리가 쓸 때

| 하고 싶은 일 | 먼저 볼 곳 |
|---|---|
| PRD의 전체 모양을 잡는다 | Atlassian PRD 템플릿 → Reforge 7 templates |
| 채워진 완성 예시를 본다 | Attract Group, Inflectra |
| 요구 문장을 정확하게 쓴다 | EARS 공식 안내, Given When Then |
| 우선순위를 정한다 | Agile Business Consortium의 MoSCoW |
| AI Agent 제품에만 필요한 항목을 점검한다 | Uvik AI PRD |
| 간트의 모양을 참고한다 | TeamGantt 예시, Miro 애자일 템플릿 |
| 간트를 코드로 관리한다 | Mermaid Gantt 문서, `gantt/make_gantt.py` |
| 한국어로 개념을 먼저 잡는다 | 이랜서, 위키백과 요구공학·요구사항 분석 |

## 5. 확인하지 못한 것

- **자동 열람이 막혀 확인하지 못함**: Smartsheet의 PRD 템플릿(`https://www.smartsheet.com/content/free-product-requirements-document-template`)과 간트 차트 페이지, Lucid 한국어 간트 튜토리얼, ISO 공식 표준 페이지. 검색 결과에는 나왔지만 이 환경에서는 열리지 않았다. 브라우저에서 직접 열어 보면 된다.
- **죽은 링크라 뺀 것**: Playcode PRD 템플릿(HTTP 410), Asana PRD 페이지(404), Agile Business Consortium의 옛 MoSCoW 주소(404), Alistair Cockburn 유스케이스 페이지(404).
- **본문까지 확인하지 못한 것**: Atlassian PRD 가이드는 페이지 존재와 제목만 확인했다.
- 외부 페이지의 내용이 정확한지는 검증하지 않았다.
