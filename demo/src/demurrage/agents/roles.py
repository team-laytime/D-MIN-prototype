"""역할별 Agent — 팀 캔버스의 '나눠 맡는 멀티 Agent'를 코드로 옮긴 것.

여기서 Agent는 '정해진 입력을 받아 정해진 출력을 내는 역할 모듈'이다(NFR-18).
- 숫자를 다루는 Agent(입력검증·제약판단·최적화·체선료계산·리스크·검증)는 LLM을 쓰지 않는다(NFR-01).
- LLM을 쓸 수 있는 것은 보고서 Agent의 문장 작성뿐이다(선택, 꺼도 템플릿으로 끝까지 돈다).
  질의응답 Agent는 팀 결정(11/09)으로 범위에서 뺐다.
- 어떤 Agent도 후보 확정·규칙 변경·삭제·발송을 하지 않는다(NFR-16). 확정은 API의 사람 동작으로만 일어난다.
순서와 데이터 전달은 오케스트레이터(코드)가 정한다 — LLM이 흐름을 정하지 않는다(ADR-005).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    code: str
    name: str
    stage: str          # 피그마 워크플로우 단계(1 입력 … 7 검증)
    does: str
    tools: tuple        # 쓸 수 있는 동작(모두 읽기·계산·초안)
    uses_llm: bool = False
    requirements: tuple = ()
    label: str = ""     # 화면에 쓰는 단계 이름(업무 용어)


AGENTS = {
    "intake": AgentSpec("intake", "입력검증 Agent", "1 입력", "시나리오를 읽고 필수값·형식·시각 순서·참조를 검사, 부두 적합성·작업시간 추정 가능 여부 확인",
                        ("parse_scenario", "check_assignability"), requirements=("FR-01", "FR-02", "FR-07", "FR-08", "FR-23"), label="입력 검증"),
    "constraint": AgentSpec("constraint", "제약판단 Agent", "2 계산", "부두 제한(정비·강풍), 야간 도선, 조석, 동시 접안 조합을 정리하고 ETB 엔진에 넘김",
                            ("weather_restrictions", "eligibility", "night_rules"), requirements=("FR-03", "FR-06", "FR-12~18", "FR-20"), label="제약 정리"),
    "optimizer": AgentSpec("optimizer", "최적화 Agent", "2 계산", "기준안(FCFS)과 총 예상 체선료가 낮은 후보 3개를 찾고 독립 검증기로 걸러 냄",
                           ("fcfs", "local_search", "branch_and_bound", "validate"), requirements=("FR-34", "FR-35", "FR-36", "NFR-08"), label="후보 탐색"),
    "demurrage": AgentSpec("demurrage", "체선료계산 Agent", "2 계산", "후보마다 선박별 정박개시·정박종료·체선 시간·체선료와 산출 근거를 만든다",
                           ("laytime", "evidence"), requirements=("FR-22", "FR-24~33", "FR-39"), label="체선료 계산"),
    "risk": AgentSpec("risk", "리스크 Agent", "4 리스크", "후보마다 5개 리스크 점검, ETA ±6시간·예보 변경 민감도",
                      ("assess", "sensitivity"), requirements=("FR-40", "FR-41", "FR-43"), label="리스크 점검"),
    "report": AgentSpec("report", "보고서 Agent", "5 보고서", "후보 제안 보고서·메일 초안. 문장만 LLM(선택), 숫자는 엔진 값",
                        ("build_facts", "narrate", "render", "audit_numbers"), uses_llm=True, requirements=("FR-44", "FR-45", "FR-46", "NFR-03", "NFR-12", "NFR-14"), label="보고서 작성"),
    "verify": AgentSpec("verify", "검증 Agent", "7 검증", "합계 = 선박별 합, 증감 합 = 절감액, 제약 위반 0, 결과 지문(재현성)",
                        ("validate", "fingerprint", "run_golden"), requirements=("FR-30", "FR-38", "FR-50", "NFR-02"), label="결과 검증"),
}

# 사람만 하는 동작 — 어떤 Agent의 도구 목록에도 없다
HUMAN_ONLY_ACTIONS = ("후보 확정(SELECT)", "확정 취소(CANCEL)", "현업 반영 완료(APPLIED)", "규칙 표 변경", "메일 발송")
