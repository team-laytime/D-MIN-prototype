package com.dmin.laytime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;

/**
 * 재검증이 실제로 잡아내는지: 솔버 값을 1센트·1분만 바꿔도, 규칙을 어긴 배정도 통과하지 못해야 한다.
 * 숫자가 다 맞아도 FIX 배를 옮겼거나 현행 계획이 입력과 다르면 통과하지 못해야 한다.
 */
class VerifierCatchesTamperingTest {

    private final Rules rules = Rules.bundled(Map.of());

    private SolverOutput.Schedule firstCandidate(JsonNode response) {
        return SolverOutput.schedules(response).stream().filter(s -> s.rank() == 1).findFirst().orElseThrow();
    }

    private CaseData data(JsonNode request) {
        return CaseParser.parse(request, rules).data();
    }

    @Test
    void oneCentOffIsCaught() throws Exception {
        JsonNode req = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/EXAMPLE-3.request.json"));
        JsonNode resp = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/EXAMPLE-3.response.json"));
        SolverOutput.Schedule s = firstCandidate(resp);
        List<Verifier.PlanInput> plans = new ArrayList<>(s.plans());
        Verifier.PlanInput p = plans.getFirst();
        plans.set(0, new Verifier.PlanInput(p.arrivalId(), p.berth(), p.etb(), p.workStart(), p.workEnd(), p.hoseOff(), p.etu(),
                p.laytimeStart(), p.cents() + 1));
        Verifier.Result r = Verifier.check("변조", rules, data(req), plans, s.totalCents() + 1, 0, true);
        assertFalse(r.pass());
        assertTrue(r.mismatches().stream().anyMatch(m -> m.contains("체선료")));
    }

    @Test
    void oneMinuteOffIsCaught() throws Exception {
        JsonNode req = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/EXAMPLE-3.request.json"));
        JsonNode resp = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/EXAMPLE-3.response.json"));
        SolverOutput.Schedule s = firstCandidate(resp);
        List<Verifier.PlanInput> plans = new ArrayList<>(s.plans());
        Verifier.PlanInput p = plans.getFirst();
        plans.set(0, new Verifier.PlanInput(p.arrivalId(), p.berth(), p.etb(), p.workStart(), p.workEnd(), p.hoseOff() + 1, p.etu(),
                p.laytimeStart(), p.cents()));
        Verifier.Result r = Verifier.check("변조", rules, data(req), plans, s.totalCents(), 0, true);
        assertFalse(r.pass());
        assertTrue(r.mismatches().stream().anyMatch(m -> m.contains("호스분리")));
    }

    @Test
    void fixedVesselMovedIsCaught() throws Exception {
        JsonNode req = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/EXAMPLE-3.request.json"));
        JsonNode resp = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/EXAMPLE-3.response.json"));
        CaseData cs = data(req);
        SolverOutput.Schedule s = firstCandidate(resp);
        // F(FIX #8 11/12 08:00)를 #1-1, 3일 뒤로 옮긴다. 시각·금액은 Java가 그 자리로 다시 계산한 값이라 숫자는 다 맞는다
        // → 'FIX는 입력 그대로' 검사만 잡을 수 있다
        CaseData.Arrival f = cs.arrivals().get("F");
        Plan q = Calc.makePlan(rules, cs, f, "#1-1", f.fix().etb() + 3 * Times.DAY, true);
        List<Verifier.PlanInput> plans = new ArrayList<>();
        long total = 0;
        for (Verifier.PlanInput p : s.plans()) {
            Verifier.PlanInput moved = "F".equals(p.arrivalId())
                    ? new Verifier.PlanInput("F", q.berth(), q.s(), q.a(), q.c(), q.h(), q.u(), q.layStart(), q.cents())
                    : p;
            plans.add(moved);
            total += moved.cents();
        }
        Verifier.Result r = Verifier.check("FIX 옮김", rules, cs, plans, total, 0, true);
        assertFalse(r.pass());
        assertEquals(List.of("F: FIX·작업 중 배의 부두·ETB가 입력과 다름 (입력 #8 11/12 08:00 ≠ 솔버 #1-1 11/15 08:00)"), r.mismatches());
    }

    @Test
    void currentPlanMustMatchTheInput() throws Exception {
        JsonNode req = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/SAMPLE-W46.request.json"));
        JsonNode resp = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/SAMPLE-W46.response.json"));
        CaseData cs = data(req);
        assertEquals(54, cs.currentPlan().size());
        SolverOutput.Schedule cur = SolverOutput.schedules(resp).stream().filter(SolverOutput.Schedule::current).findFirst().orElseThrow();
        // 정답의 현행 계획은 입력의 부두·ETB 그대로라 통과한다 (규칙 위반은 솔버가 센 수와 같으면 된다)
        Verifier.Result same = Verifier.check(cur.name(), rules, cs, cur.plans(), cur.totalCents(), cur.violations(), false, cs.currentPlan());
        assertTrue(same.pass(), same.mismatches()::toString);

        // 움직일 수 있는 배 하나의 부두만 바꾼다. 시각·금액은 Java가 새 부두로 다시 계산한 값 → '현행 계획 = 입력' 검사만 잡는다
        List<Verifier.PlanInput> plans = new ArrayList<>(cur.plans());
        int i = 0;
        while (!cs.arrivals().get(plans.get(i).arrivalId()).movable()) {
            i++;
        }
        Verifier.PlanInput p = plans.get(i);
        String other = rules.berthOrder().stream().filter(b -> !b.equals(p.berth())).findFirst().orElseThrow();
        Plan q = Calc.makePlan(rules, cs, cs.arrivals().get(p.arrivalId()), other, p.etb(), false);
        plans.set(i, new Verifier.PlanInput(p.arrivalId(), other, q.s(), q.a(), q.c(), q.h(), q.u(), q.layStart(), q.cents()));
        long total = plans.stream().mapToLong(Verifier.PlanInput::cents).sum();
        Verifier.Result r = Verifier.check(cur.name(), rules, cs, plans, total, cur.violations(), false, cs.currentPlan());
        assertFalse(r.pass());
        assertTrue(r.mismatches().stream().anyMatch(m -> m.startsWith(p.arrivalId() + ": 현행 계획의 부두·ETB가 입력과 다름")),
                r.mismatches()::toString);

        // 입력에 있는 배가 솔버 일정에서 빠져도 잡는다
        List<Verifier.PlanInput> fewer = new ArrayList<>(cur.plans());
        Verifier.PlanInput gone = fewer.removeLast();
        Verifier.Result r2 = Verifier.check(cur.name(), rules, cs, fewer, cur.totalCents() - gone.cents(), cur.violations(), false,
                cs.currentPlan());
        assertTrue(r2.mismatches().contains(gone.arrivalId() + ": 현행 계획 입력에는 있는데 솔버 일정에 없음"), r2.mismatches()::toString);
    }

    @Test
    void sameBerthOverlapIsAViolation() throws Exception {
        JsonNode req = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/EXAMPLE-3.request.json"));
        CaseData cs = data(req);
        // A와 C를 같은 #6에 같은 시각으로 놓는다 → 같은 부두 충돌
        long etb = Times.parse("2026-11-10T09:00");
        List<Plan> plans = new ArrayList<>();
        for (CaseData.Arrival a : cs.arrivals().values()) {
            String berth = a.movable() ? "#6" : a.fix().berth();
            long s = a.movable() ? etb : a.fix().etb();
            plans.add(Calc.makePlan(rules, cs, a, berth, s, !a.movable()));
        }
        List<String> v = Verifier.violations(rules, cs, plans);
        assertTrue(v.stream().anyMatch(x -> x.contains("같은 부두 충돌")), v::toString);
    }
}
