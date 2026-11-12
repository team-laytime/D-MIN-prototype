"""보고서 Agent — LLM은 문장만(숫자 검문), 비용 상한, 전송 항목 제한, 단정 표현 금지, 숫자 대조 0건."""
import json

from demurrage.agents.orchestrator import run_pipeline
from demurrage.llm.adapter import CostMeter, LLMClient, LLMResult, guard_text
from demurrage.report.builder import audit_numbers, build_facts, llm_narrative


class FakeLLM(LLMClient):
    name = "fake"
    model = "claude-opus-5-5"

    def __init__(self, payload, cost=0.01):
        self.payload, self.cost, self.calls = payload, cost, 0

    def available(self):
        return True

    def complete(self, system, user, schema=None, max_tokens=4000):
        self.calls += 1
        self.last_user = user
        return LLMResult(ok=True, text=json.dumps(self.payload, ensure_ascii=False), model=self.model,
                         input_tokens=3000, output_tokens=600, cost_usd=self.cost)


GOOD = {"summary": "1안은 기준안 {{base_total}}보다 {{c1_saving}} 낮습니다.",
        "recommendation_reason": "V05를 폭풍 전에 접안해 대기를 없앴습니다. 1안 총액은 {{c1_total}}입니다.",
        "candidate_notes": [{"candidate": "1안", "note": "절감 {{c1_saving_pct}}"}],
        "mail_intro": "후보를 비교해 보내 드립니다.", "caution_note": "가상 데이터 기반 초안입니다."}


def test_llm_text_with_placeholders_is_used_and_numbers_come_from_engine(s5):
    run = run_pipeline(s5, llm=FakeLLM(GOOD), with_sensitivity=False)
    nar = run["report"]["narrative"]
    assert nar["generated_by"].startswith("LLM(")
    assert run["baseline"]["total_display"] in nar["summary"] and run["candidates"][0]["savings_display"] in nar["summary"]
    assert run["report"]["audit"]["report"]["mismatches"] == []
    assert run["llm"]["calls"] == 1 and run["llm"]["cost_usd"] > 0


def test_llm_text_with_raw_numbers_is_rejected():
    bad = dict(GOOD, summary="1안은 25,431달러 절감합니다.")
    assert guard_text(bad["summary"], {"1안"}) == ["25,431"]


def test_pipeline_falls_back_to_template_when_llm_writes_numbers(s5):
    bad = dict(GOOD, recommendation_reason="V05는 11/11 02:30에 접안합니다.")
    run = run_pipeline(s5, llm=FakeLLM(bad), with_sensitivity=False)
    assert run["report"]["narrative"]["generated_by"] == "template"
    assert "숫자" in run["report"]["narrative_source"]


def test_cost_cap_stops_llm_and_uses_template(s5):
    fake = FakeLLM(GOOD)
    run = run_pipeline(s5, llm=fake, cost_cap_usd=0.0001, with_sensitivity=False)
    assert fake.calls == 0 and run["report"]["narrative"]["generated_by"] == "template"
    assert "비용 상한" in run["report"]["narrative_source"]


def test_facts_sent_to_llm_exclude_rates_names_and_remarks(s5_run):
    facts, _ = build_facts(s5_run)
    blob = json.dumps(facts, ensure_ascii=False)
    for v in s5_run["input"]["vessels"]:
        assert v["name"] not in blob                                  # 선박명 원문
        if v.get("remarks"):
            assert v["remarks"] not in blob                            # 자유 입력 문장
    assert "rate" not in blob and "demurrage_rate" not in blob          # 계약 요율 필드 없음


def test_report_and_mail_numbers_match_engine_and_no_forbidden_phrases(s5_run):
    assert s5_run["report"]["audit"]["report"]["mismatches"] == []
    assert s5_run["report"]["audit"]["mail"]["mismatches"] == []
    for f in ["지금 확정", "확정하세요", "자동 확정"]:
        assert f not in s5_run["report"]["markdown"] and f not in s5_run["mail"]["body"]
    assert "담당자 검토용 초안" in s5_run["report"]["markdown"]
    for c in s5_run["candidates"]:
        for r in s5_run["risks"][c["label"]]:
            assert r["status"] in ("APPLIES", "NOT_APPLICABLE", "UNKNOWN")
            if r["status"] != "NOT_APPLICABLE":
                assert r["alternative"] and r["caution"]
        assert len(s5_run["risks"][c["label"]]) == 5


def test_audit_catches_a_wrong_number(s5_run):
    tampered = s5_run["report"]["markdown"].replace(s5_run["candidates"][0]["total_display"], "$1,234,567", 1)
    assert "$1,234,567" in audit_numbers(tampered, s5_run)["mismatches"]
