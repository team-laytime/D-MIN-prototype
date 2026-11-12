# demo/docs — 문서 색인

울산 CLX 체선료 플래너(척화비) 파이프라인 데모의 설계·결정·검증 문서입니다. 처음이면 **00 최종 보고서**만 읽어도 전체가 보입니다. v0.2(2026-11-09 오후)에서 계약서·시나리오·화면 설계 문서(10~12)와 아키텍처 다이어그램을 더했고, 질의응답 Agent를 뺐습니다.

| 순서 | 문서 | 이런 사람에게 |
|---|---|---|
| 00 | [최종 보고서](00-final-report.md) | 모두 — 무엇을 만들었고, 어떻게 돌리고, 왜 이렇게 만들었나 |
| 01 | [아키텍처](01-architecture.md) | BE·Infra — 계층·경계·데이터 흐름, 피그마 단계 ↔ 코드 |
| 02 | [백엔드](02-backend.md) | BE — API·DB·엔진 모듈·입력 형식 |
| 03 | [AI·처리 단계](03-ai-agents.md) | AI/DATA — 역할 모듈, LLM 경계(숫자 검문), 권한·비용 |
| 04 | [인프라·DevOps](04-infra-devops.md) | Infra — 컨테이너·CI 문지기·관측·보안·운영 단계 |
| 05 | [최적화](05-optimization.md) | AI/DATA — 수리 모델(기호 + 한글), 분기한정, 증명 요지, 성능 |
| 06 | [규칙과 정답 세트](06-rules-and-golden-set.md) | 모두 — 규칙 ID 표, 손계산 풀이, 정답 추가법 |
| 07 | [실행 대본](07-run-scenario.md) | 발표·멘토링 — 화면별로 누를 것·말할 것·숫자 |
| 08 | [요구사항 추적표](08-traceability.md) | PM — FR 52·NFR 21 ↔ 구현 ↔ 확인 |
| 09 | [현업 질문](09-open-questions.md) | PM·멘토링 — 규칙을 옮기며 생긴 질문 |
| 10 | [계약서 예시](10-contracts.md) | 모두 — 가상 계약서 23건, 조항 ↔ 엔진 규칙, 계산서 근거 |
| 11 | [시나리오 라이브러리](11-scenarios.md) | 모두 — 16가지 상황, 결과, 근거 |
| 12 | [화면 설계](12-ui-design.md) | FE·기획 — SEAGATE 개선 컨셉, 정보 구조, 디자인 원칙·토큰 |
| 13 | [수리계획법](13-math-programming.md) | AI/DATA·모두 — 접안 계획을 변수·목적함수·제약식으로. 두 타입: [13a 주제 설명 문서 기준](13a-math-programming-brief.md) · [13b 멘토링 PPT 기준](13b-math-programming-ppt.md), 공유용 페이지는 assets/ |
| 14 | [EKS 배포 준비](14-eks-architecture.md) | Infra·모두 — 설정 이유·현재 데모와 목표 구조·팀의 운영 작업, [배포 명령](../deploy/README.md) |
| 16 | [실시간 공공 데이터 연결](16-live-data.md) | 모두 — 선박 위치·ETA 연결 현황, 예시 시나리오, Pain point·장애 지점, 키 관리 |
| ADR | [결정 기록](adr/README.md) | 모두 — 트레이드오프 15개(014·015는 11-10에 덧붙인 Spring Boot + LangGraph 방향) |

그림·산출물: [`assets/`](assets/) — 프로젝트·백엔드 아키텍처 다이어그램(SVG), 대표 데모(S05)의 기준안·1안 타임라인, 보고서(.md·.html), 메일 초안.
