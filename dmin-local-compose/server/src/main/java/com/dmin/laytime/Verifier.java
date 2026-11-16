package com.dmin.laytime;

import com.dmin.laytime.CaseData.Arrival;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 솔버가 낸 일정을 Spring이 처음부터 다시 계산해 본다 (정의서 4.2·5.1-5: "솔버 결과는 제안일 뿐, Spring이 재검증").
 * 금액·시각은 이 클래스가 다시 낸 값이 기준이다. 솔버 값과 1센트·1분이라도 다르면 그 후보는 '재검증 실패'로 표시되고
 * 고를 수 없다(결정 API가 막는다).
 */
public final class Verifier {

    /** 솔버가 낸 작업계획 한 줄 (응답 JSON의 plans[]). */
    public record PlanInput(
            String arrivalId, String berth, long etb, Long workStart, Long workEnd, Long hoseOff, Long etu, Long laytimeStart, long cents) {}

    public record Result(
            String name,
            int plans,
            long solverCents,
            long springCents,
            int solverViolations,
            List<String> springViolations,
            List<String> mismatches,
            boolean pass) {}

    private Verifier() {}

    /**
     * @param requireClean true면 규칙 위반 0이어야 통과(기준안·후보). false면 위반 수가 솔버와 같으면 통과(사람이 짠 현행 계획).
     */
    public static Result check(
            String name, Rules rules, CaseData cs, List<PlanInput> given, long solverTotalCents, int solverViolations, boolean requireClean) {
        return check(name, rules, cs, given, solverTotalCents, solverViolations, requireClean, null);
    }

    /**
     * @param expected null이 아니면 모든 작업계획의 부두·ETB가 이 값(요청의 current_plan)과 같아야 하고, 여기 있는 입항 건이 모두 나와야 한다.
     *     솔버의 '현행 계획'이 사람이 짠 입력을 그대로 계산했는지 본다.
     */
    public static Result check(
            String name,
            Rules rules,
            CaseData cs,
            List<PlanInput> given,
            long solverTotalCents,
            int solverViolations,
            boolean requireClean,
            Map<String, CaseData.CurrentPlan> expected) {
        List<String> mismatches = new ArrayList<>();
        List<Plan> again = new ArrayList<>();
        Map<String, PlanInput> byId = new LinkedHashMap<>();
        for (PlanInput p : given) {
            if (byId.put(p.arrivalId(), p) != null) {
                mismatches.add(p.arrivalId() + ": 작업계획이 두 번 나옴");
            }
            if (expected != null) {
                CaseData.CurrentPlan want = expected.get(p.arrivalId());
                if (want == null) {
                    mismatches.add(p.arrivalId() + ": 현행 계획 입력에 없는 입항 건");
                } else if (!want.berth().equals(p.berth()) || want.etb() != p.etb()) {
                    mismatches.add(p.arrivalId() + ": 현행 계획의 부두·ETB가 입력과 다름 (입력 " + want.berth() + " " + Times.fmt(want.etb())
                            + " ≠ 솔버 " + p.berth() + " " + Times.fmt(p.etb()) + ")");
                }
            }
            Arrival a = cs.arrivals.get(p.arrivalId());
            if (a == null) {
                mismatches.add(p.arrivalId() + ": 입력에 없는 입항 건");
                continue;
            }
            // FIX·작업 중은 다시 짜지 않는다: 솔버가 부두·ETB를 옮겼으면 시각·금액이 맞아도 통과시키지 않는다
            CaseData.Fix fx = a.fix();
            if (!a.movable() && fx != null && (!fx.berth().equals(p.berth()) || fx.etb() != p.etb())) {
                mismatches.add(a.id() + ": FIX·작업 중 배의 부두·ETB가 입력과 다름 (입력 " + fx.berth() + " " + Times.fmt(fx.etb())
                        + " ≠ 솔버 " + p.berth() + " " + Times.fmt(p.etb()) + ")");
            }
            if (!rules.berths.containsKey(p.berth())) {
                mismatches.add(p.arrivalId() + ": 없는 부두 " + p.berth());
                continue;
            }
            Plan q = Calc.makePlan(rules, cs, a, p.berth(), p.etb(), !a.movable());
            again.add(q);
            same(mismatches, a.id(), "작업시작", p.workStart(), q.a());
            same(mismatches, a.id(), "작업완료", p.workEnd(), q.c());
            same(mismatches, a.id(), "호스분리", p.hoseOff(), q.h());
            same(mismatches, a.id(), "이안", p.etu(), q.u());
            same(mismatches, a.id(), "정박개시", p.laytimeStart(), q.layStart());
            if (p.cents() != q.cents()) {
                mismatches.add(String.format("%s: 체선료 솔버 $%,.2f ≠ Spring $%,.2f", a.id(), p.cents() / 100.0, q.cents() / 100.0));
            }
        }
        if (expected != null) {
            for (String id : expected.keySet()) {
                if (!byId.containsKey(id)) {
                    mismatches.add(id + ": 현행 계획 입력에는 있는데 솔버 일정에 없음");
                }
            }
        }
        List<String> violations = violations(rules, cs, again);
        long springTotal = again.stream().mapToLong(Plan::cents).sum();
        if (springTotal != solverTotalCents) {
            mismatches.add(String.format("총액 솔버 $%,.2f ≠ Spring $%,.2f", solverTotalCents / 100.0, springTotal / 100.0));
        }
        boolean pass = mismatches.isEmpty() && (requireClean ? violations.isEmpty() : violations.size() == solverViolations);
        return new Result(name, given.size(), solverTotalCents, springTotal, solverViolations, violations, mismatches, pass);
    }

    private static void same(List<String> out, String id, String what, Long solver, long spring) {
        if (solver != null && solver != spring) {
            out.add(id + ": " + what + " 솔버 " + Times.fmt(solver) + " ≠ Spring " + Times.fmt(spring));
        }
    }

    /** 일정 하나가 PPT 규칙을 모두 지키는지 (Python planner.verify와 같은 검사). */
    public static List<String> violations(Rules rules, CaseData cs, List<Plan> plans) {
        List<String> bad = new ArrayList<>();
        Map<String, Plan> got = new HashMap<>();
        for (Plan p : plans) {
            got.put(p.aid(), p);
        }
        for (Arrival a : cs.arrivals.values()) {
            Plan p = got.get(a.id());
            if (p == null) {
                bad.add(a.id() + ": 작업계획 없음");
                continue;
            }
            if (a.movable()) {
                List<String> why = Calc.ineligible(rules, a, p.berth());
                if (!why.isEmpty()) {
                    bad.add(a.id() + ": " + p.berth() + " 배정 불가 — " + String.join("; ", why));
                }
                if (p.s() < Calc.tau0(rules, a, p.berth())) {
                    bad.add(a.id() + ": ETB " + Times.fmt(p.s()) + " < ETA + Direction");
                }
                Calc.Window w = Calc.phi(Calc.windowsOf(rules, cs, a, p.berth()), p.s());
                if (w.from() != p.s()) {
                    bad.add(a.id() + ": ETB " + Times.fmt(p.s()) + "가 금지 구간 안 (" + w.tag() + ")");
                }
                if (p.u() > cs.end) {
                    bad.add(a.id() + ": 이안 " + Times.fmt(p.u()) + "이 계획 종료 뒤");
                }
            }
        }
        for (int i = 0; i < plans.size(); i++) {
            for (int j = i + 1; j < plans.size(); j++) {
                String why = Calc.conflict(rules, cs, plans.get(i), plans.get(j));
                if (why != null) {
                    bad.add(plans.get(i).aid() + "·" + plans.get(j).aid() + ": " + why + " 충돌");
                }
            }
        }
        bad.addAll(Calc.tankViolations(cs, plans));
        return bad;
    }
}
