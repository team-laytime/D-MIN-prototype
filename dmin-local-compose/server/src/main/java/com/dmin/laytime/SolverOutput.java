package com.dmin.laytime;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import tools.jackson.databind.JsonNode;

/**
 * Python 에이전트 응답 JSON(run.optimize)에서 검산할 일정들을 꺼낸다: 현행 계획 · 기준안 · 1~3안.
 * 모양이 계약과 다르면(꼭 있어야 할 칸이 없음 · 배열이 아님 · rank가 정수가 아님) IllegalArgumentException을 던진다.
 */
public final class SolverOutput {

    /** current = 사람이 짠 '현행 계획'(요청의 current_plan을 그대로 계산한 일정)일 때만 true. */
    public record Schedule(
            String name, int rank, List<Verifier.PlanInput> plans, long totalCents, int violations, boolean requireClean, boolean current) {}

    private SolverOutput() {}

    public static List<Schedule> schedules(JsonNode resp) {
        if (resp == null || !resp.isObject()) {
            throw new IllegalArgumentException("솔버 응답: 최상위가 JSON 객체가 아님");
        }
        List<Schedule> out = new ArrayList<>();
        if (resp.hasNonNull("current_plan")) {
            out.add(schedule("현행 계획", 0, resp.get("current_plan"), "current_plan", false, true));
        }
        if (resp.hasNonNull("baseline")) {
            out.add(schedule("기준안", 0, resp.get("baseline"), "baseline", true, false));
        }
        Set<Integer> ranks = new HashSet<>();
        int n = 0;
        for (JsonNode c : array(resp, "candidates", "최상위").values()) {
            n++;
            String where = "candidates[" + n + "]";
            int rank = rank(c, where);
            if (!ranks.add(rank)) {
                throw new IllegalArgumentException("솔버 응답: " + where + "의 rank " + rank + "가 중복");
            }
            out.add(schedule(rank + "안", rank, c, where, true, false));
        }
        return out;
    }

    static Schedule schedule(String name, int rank, JsonNode s, String where, boolean requireClean, boolean current) {
        List<Verifier.PlanInput> plans = new ArrayList<>();
        int k = 0;
        for (JsonNode p : array(s, "plans", where).values()) {
            k++;
            String at = where + ".plans[" + k + "]";
            plans.add(new Verifier.PlanInput(
                    text(p, "arrival_id", at),
                    text(p, "berth", at),
                    time(p, "etb", at),
                    opt(p, "work_start", at),
                    opt(p, "work_end", at),
                    opt(p, "hose_off", at),
                    opt(p, "etu", at),
                    opt(p, "laytime_start", at),
                    cents(p, "demurrage_usd", at)));
        }
        return new Schedule(
                name, rank, plans, cents(s, "total_usd", where), array(s, "violations", where).size(), requireClean, current);
    }

    private static boolean blank(JsonNode v) {
        return v == null || v.isNull() || (v.isString() && v.asString().isBlank());
    }

    private static IllegalArgumentException missing(String where, String field) {
        return new IllegalArgumentException("솔버 응답: " + where + "에 " + field + " 없음");
    }

    private static int rank(JsonNode c, String where) {
        JsonNode v = c.get("rank");
        if (blank(v)) {
            throw missing(where, "rank");
        }
        if (!v.isIntegralNumber() || !v.canConvertToInt() || v.intValue() < 1) {
            throw new IllegalArgumentException("솔버 응답: " + where + ".rank는 1 이상의 정수여야 함: " + v);
        }
        return v.intValue();
    }

    private static JsonNode array(JsonNode node, String field, String where) {
        JsonNode v = node.get(field);
        if (v == null || v.isNull()) {
            throw missing(where, field);
        }
        if (!v.isArray()) {
            throw new IllegalArgumentException("솔버 응답: " + where + "." + field + "가 배열이 아님");
        }
        return v;
    }

    private static String text(JsonNode node, String field, String where) {
        JsonNode v = node.get(field);
        if (blank(v)) {
            throw missing(where, field);
        }
        if (!v.isString()) {
            throw new IllegalArgumentException("솔버 응답: " + where + "." + field + "가 문자열이 아님: " + v);
        }
        return v.asString();
    }

    private static long time(JsonNode node, String field, String where) {
        String s = text(node, field, where);
        try {
            return Times.parse(s);
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("솔버 응답: " + where + "." + field + ": " + e.getMessage());
        }
    }

    /** 없거나 null이면 null(검산에서 비교하지 않음). 값이 있으면 시각이어야 한다. */
    private static Long opt(JsonNode node, String field, String where) {
        JsonNode v = node.get(field);
        return v == null || v.isNull() ? null : time(node, field, where);
    }

    private static long cents(JsonNode node, String field, String where) {
        JsonNode v = node.get(field);
        if (blank(v)) {
            throw missing(where, field);
        }
        if (!v.isNumber() || !Double.isFinite(v.doubleValue())) {
            throw new IllegalArgumentException("솔버 응답: " + where + "." + field + "가 숫자가 아님: " + v);
        }
        return cents(v);
    }

    /** 응답의 달러(소수 둘째 자리) → 센트. 응답은 센트/100을 그대로 낸 값이라 반올림하면 원래 센트가 된다. */
    static long cents(JsonNode usd) {
        return Math.round(usd.doubleValue() * 100);
    }
}
