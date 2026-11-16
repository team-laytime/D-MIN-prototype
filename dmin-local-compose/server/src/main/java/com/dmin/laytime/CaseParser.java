package com.dmin.laytime;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import tools.jackson.databind.JsonNode;

/**
 * 요청 JSON → CaseData. 들어오는 데이터의 입구 검사(FR-01~04)도 여기서 한다.
 * errors가 하나라도 있으면 실행하지 않는다. warnings는 실행은 하되 화면에 보여 준다.
 */
public final class CaseParser {

    public record Parsed(CaseData data, List<String> errors, List<String> warnings) {
        public boolean ok() {
            return errors.isEmpty();
        }
    }

    private static final Set<String> STATUS = Set.of("PLANNED", "FIX", "WORKING");
    private static final Set<String> REASONS = Set.of("WEATHER", "WORK");

    private final Rules rules;
    private final List<String> errors = new ArrayList<>();
    private final List<String> warnings = new ArrayList<>();

    private CaseParser(Rules rules) {
        this.rules = rules;
    }

    public static Parsed parse(JsonNode doc, Rules rules) {
        return new CaseParser(rules).run(doc);
    }

    private Parsed run(JsonNode doc) {
        if (doc == null || !doc.isObject()) {
            errors.add("최상위가 JSON 객체가 아님");
            return new Parsed(null, errors, warnings);
        }
        JsonNode plan = doc.path("plan");
        Long start = time(plan.get("start"), "plan.start", true);
        Long end = time(plan.get("end"), "plan.end", true);
        if (start != null && end != null && start >= end) {
            errors.add("plan.start가 plan.end보다 늦거나 같음");
        }
        LinkedHashMap<String, CaseData.Arrival> arrivals = new LinkedHashMap<>();
        JsonNode arr = doc.get("arrivals");
        if (arr == null || !arr.isArray() || arr.isEmpty()) {
            errors.add("arrivals가 비어 있음 (입항 건이 한 척 이상 있어야 함)");
        } else {
            int n = 0;
            for (JsonNode v : arr.values()) {
                n++;
                CaseData.Arrival a = arrival(v, n);
                if (a == null) {
                    continue;
                }
                if (arrivals.containsKey(a.id())) {
                    errors.add("arrivals[" + n + "]: id '" + a.id() + "'가 중복");
                    continue;
                }
                arrivals.put(a.id(), a);
            }
        }
        List<CaseData.Restriction> restrictions = new ArrayList<>();
        int rn = 0;
        for (JsonNode r : doc.path("restrictions").values()) {
            rn++;
            String where = "restrictions[" + rn + "]";
            String id = req(r, "id", where);
            String reason = req(r, "reason", where);
            if (reason != null && !REASONS.contains(reason)) {
                errors.add(where + ".reason은 WEATHER 또는 WORK: '" + reason + "'");
            }
            List<String> berths = new ArrayList<>();
            if (r.has("berths")) {
                JsonNode bs = r.get("berths");
                // "*"처럼 문자열 하나를 주면 values()가 비어 제약이 어느 부두에도 걸리지 않는다 → 배열만 받는다
                if (!bs.isArray() || bs.isEmpty() || !bs.values().stream().allMatch(JsonNode::isString)) {
                    errors.add(where + ".berths는 문자열 배열이어야 함 (전 부두는 [\"*\"])");
                } else {
                    for (JsonNode b : bs.values()) {
                        String bid = b.asString();
                        if (!"*".equals(bid) && !rules.berths.containsKey(bid)) {
                            errors.add(where + ".berths에 없는 부두 '" + bid + "'");
                        }
                        berths.add(bid);
                    }
                }
            } else {
                berths.add("*");
            }
            Long s = time(r.get("start"), where + ".start", true);
            Long e = time(r.get("end"), where + ".end", true);
            if (s != null && e != null && s >= e) {
                errors.add(where + ": start가 end보다 늦거나 같음");
            }
            if (id != null && reason != null && s != null && e != null) {
                restrictions.add(new CaseData.Restriction(id, reason, berths, s, e));
            }
        }
        List<CaseData.Tank> tanks = new ArrayList<>();
        int tn = 0;
        for (JsonNode t : doc.path("inventory").values()) {
            tn++;
            String where = "inventory[" + tn + "]";
            String group = req(t, "group", where);
            Double opening = number(t.get("opening"), where + ".opening", true);
            Double min = number(t.get("min"), where + ".min", true);
            Double max = number(t.get("max"), where + ".max", true);
            List<CaseData.Flow> flows = new ArrayList<>();
            int fn = 0;
            for (JsonNode f : t.path("flows").values()) {
                fn++;
                Long f0 = time(f.get("from"), where + ".flows[" + fn + "].from", true);
                Long f1 = time(f.get("to"), where + ".flows[" + fn + "].to", true);
                Double use = number(f.get("use_per_h"), where + ".flows[" + fn + "].use_per_h", true);
                if (f0 != null && f1 != null && use != null) {
                    flows.add(new CaseData.Flow(f0, f1, use));
                }
            }
            if (group != null && opening != null && min != null && max != null) {
                if (min > max) {
                    errors.add(where + ": min이 max보다 큼");
                }
                tanks.add(new CaseData.Tank(group, opening, min, max, flows));
            }
        }
        Map<Long, long[]> sun = new HashMap<>();
        JsonNode sunNode = doc.path("sun");
        for (String day : sunNode.propertyNames()) {
            JsonNode pair = sunNode.get(day);
            try {
                long d = Times.parse(day + "T00:00");
                sun.put(d, new long[] {
                    Times.parse(day + "T" + pair.get(0).asString()), Times.parse(day + "T" + pair.get(1).asString())
                });
            } catch (RuntimeException ex) {
                errors.add("sun['" + day + "']는 [\"HH:MM\", \"HH:MM\"] (일출, 일몰)");
            }
        }
        Set<String> seenPlan = new HashSet<>();
        Map<String, CaseData.CurrentPlan> currentPlan = new LinkedHashMap<>();
        int cn = 0;
        for (JsonNode c : doc.path("current_plan").values()) {
            cn++;
            String where = "current_plan[" + cn + "]";
            String id = req(c, "id", where);
            String berth = req(c, "berth", where);
            Long etb = time(c.get("etb"), where + ".etb", true);
            if (id != null && !arrivals.isEmpty() && !arrivals.containsKey(id)) {
                errors.add(where + ": arrivals에 없는 id '" + id + "'");
            }
            if (berth != null && !rules.berths.containsKey(berth)) {
                errors.add(where + ": 없는 부두 '" + berth + "'");
            }
            if (id != null && !seenPlan.add(id)) {
                errors.add(where + ": id '" + id + "'가 중복");
                continue;
            }
            CaseData.Arrival fixed = id == null ? null : arrivals.get(id);
            if (fixed != null && !fixed.movable() && fixed.fix() != null && berth != null && etb != null
                    && (!fixed.fix().berth().equals(berth) || fixed.fix().etb() != etb)) {
                errors.add(where + ": " + id + "는 " + fixed.status() + "라 fix와 같은 부두·ETB여야 함 (fix " + fixed.fix().berth() + " "
                        + Times.iso(fixed.fix().etb()) + ")");
            }
            if (id != null && berth != null && etb != null) {
                currentPlan.put(id, new CaseData.CurrentPlan(berth, etb)); // 재검증이 솔버의 '현행 계획'과 맞춰 본다
            }
        }
        JsonNode opts = doc.path("options");
        if (!opts.isMissingNode() && !opts.isNull() && !opts.isObject()) {
            errors.add("options는 객체여야 함");
        } else {
            JsonNode gen = opts.path("generation");
            if (!gen.isMissingNode() && !(gen.isString() && Set.of("auto", "EXACT", "GRID").contains(gen.asString()))) {
                errors.add("options.generation은 auto·EXACT·GRID 중 하나: " + gen);
            }
            optionRange(opts, "grid_min", 5, 240, true);
            optionRange(opts, "max_wait_h", 0, 720, false);
            optionRange(opts, "inventory_wait_step_h", 0.25, 24, false);
            optionRange(opts, "inventory_wait_max_h", 0, 720, false);
        }
        String basis = doc.path("options").path("weather_basis").isString()
                ? doc.path("options").path("weather_basis").asString()
                : rules.wxBasis;
        if (!Set.of("USED", "DEMURRAGE", "WAIT").contains(basis)) {
            errors.add("weather_basis는 USED·DEMURRAGE·WAIT 중 하나: '" + basis + "'");
        }
        if (!errors.isEmpty() || start == null || end == null) {
            return new Parsed(null, errors, warnings);
        }
        String id = doc.path("id").isString() ? doc.get("id").asString() : "case";
        String title = doc.path("title").isString() ? doc.get("title").asString() : "";
        CaseData data = new CaseData(id, title, start, end, arrivals, restrictions, tanks, sun, basis, currentPlan);
        for (CaseData.Arrival a : arrivals.values()) {
            if (a.eta() >= end) {
                warnings.add(a.id() + ": ETA " + Times.iso(a.eta()) + "가 계획 종료 뒤");
            }
            if (a.movable() && Calc.eligibleBerths(rules, a).isEmpty()) {
                warnings.add(a.id() + ": 배정 가능한 부두가 없음 (제품 그룹 " + a.cargo() + "·제원 확인) → 후보 없음이 됨");
            }
        }
        return new Parsed(data, errors, warnings);
    }

    private CaseData.Arrival arrival(JsonNode v, int n) {
        String where = "arrivals[" + n + "]";
        String id = req(v, "id", where);
        if (id != null) {
            where = "arrivals[" + n + "] (" + id + ")";
        }
        String vessel = v.path("vessel").isString() ? v.get("vessel").asString() : id;
        String vclass = req(v, "class", where);
        if (vclass != null && !rules.productClasses.contains(vclass)) {
            errors.add(where + ".class는 " + rules.productClasses + " 중 하나: '" + vclass + "'");
        }
        String biz = req(v, "biz", where);
        if (biz != null && !rules.bizCodes.contains(biz)) {
            errors.add(where + ".biz는 " + rules.bizCodes + " 중 하나: '" + biz + "'");
        }
        String cargo = req(v, "cargo_group", where);
        if (v.has("qty") && absent(v.get("qty"))) {
            errors.add(where + ".qty가 비어 있음 (없으면 칸을 빼고, 물량이 0이면 0)");
        }
        Double qty = number(v.get("qty"), where + ".qty", false);
        if (qty != null && qty < 0) {
            errors.add(where + ".qty는 0 이상");
        }
        Long eta = time(v.get("eta"), where + ".eta", true);
        Long nor = time(v.get("nor_tender"), where + ".nor_tender", false);
        Double grt = number(v.get("grt"), where + ".grt", true);
        Double dwt = number(v.get("dwt"), where + ".dwt", true);
        Double loa = number(v.get("loa"), where + ".loa", true);
        Double pbl = number(v.get("pbl"), where + ".pbl", true);
        Double draft = number(v.get("draft"), where + ".draft", true);
        CaseData.Contract contract = null;
        JsonNode c = v.get("contract");
        if (c == null || !c.isObject()) {
            errors.add(where + ".contract가 없음 (laycan_from·laycan_to·laytime_h·rate_usd_day)");
        } else {
            Long lf = time(c.get("laycan_from"), where + ".contract.laycan_from", true);
            Long lt = time(c.get("laycan_to"), where + ".contract.laycan_to", true);
            Double laytime = number(c.get("laytime_h"), where + ".contract.laytime_h", true);
            Double rate = number(c.get("rate_usd_day"), where + ".contract.rate_usd_day", true);
            boolean cfr = flag(c, "cfr", where + ".contract.cfr", false);
            boolean half = flag(c, "weather_half", where + ".contract.weather_half", true);
            if (lf != null && lt != null && laytime != null && rate != null) {
                if (lf > lt) {
                    errors.add(where + ": laycan_from이 laycan_to보다 늦음");
                }
                if (laytime < 0 || rate < 0) {
                    errors.add(where + ": laytime_h·rate_usd_day는 0 이상");
                }
                contract = new CaseData.Contract(lf, lt, Times.mins(laytime), (long) Math.rint(rate * 100), cfr, half);
            }
        }
        JsonNode w = v.path("work");
        Double hours = number(w.get("hours"), where + ".work.hours", false);
        if (hours != null && hours < 0) {
            errors.add(where + ".work.hours는 0 이상");
        }
        Double ratePerH = number(w.get("rate_per_h"), where + ".work.rate_per_h", false);
        if (ratePerH != null && ratePerH <= 0) {
            errors.add(where + ".work.rate_per_h는 0보다 커야 함");
        }
        Map<String, Double> byBerth = null;
        if (w.hasNonNull("by_berth")) {
            byBerth = new LinkedHashMap<>();
            JsonNode bb = w.get("by_berth");
            if (!bb.isObject()) {
                errors.add(where + ".work.by_berth는 {\"부두\": 시간당 하역량} 객체여야 함");
            }
            for (String bid : bb.propertyNames()) {
                Double rate = number(bb.get(bid), where + ".work.by_berth." + bid, true);
                if (rate != null && rate <= 0) {
                    errors.add(where + ".work.by_berth." + bid + "는 0보다 커야 함");
                }
                byBerth.put(bid, rate);
            }
        }
        if (hours == null && ratePerH == null && (byBerth == null || byBerth.isEmpty())) {
            errors.add(where + ".work에 hours(작업시간) 또는 rate_per_h(시간당 평균 하역량)가 필요");
        }
        if (id != null && !v.has("qty") && absent(w.get("hours"))) {
            warnings.add(id + ": qty 없음 → 물량 0, 작업시간 0으로 계산");
        }
        String status = v.path("status").isString() ? v.get("status").asString() : "PLANNED";
        if (!STATUS.contains(status)) {
            errors.add(where + ".status는 PLANNED·FIX·WORKING 중 하나: '" + status + "'");
        }
        CaseData.Fix fix = null;
        if (!"PLANNED".equals(status) || v.has("fix")) {
            JsonNode f = v.path("fix");
            String fb = f.path("berth").isString() ? f.get("berth").asString() : null;
            Long fe = time(f.get("etb"), where + ".fix.etb", !"PLANNED".equals(status));
            if (!"PLANNED".equals(status) && fb == null) {
                errors.add(where + ": " + status + "이면 fix.berth·fix.etb가 필요");
            }
            if (fb != null && !rules.berths.containsKey(fb)) {
                errors.add(where + ".fix.berth에 없는 부두 '" + fb + "'");
            }
            if (fb != null && fe != null) {
                fix = new CaseData.Fix(
                        fb,
                        fe,
                        time(f.get("etu"), where + ".fix.etu", false),
                        time(f.get("work_start"), where + ".fix.work_start", false));
            }
        }
        List<String> berths = null;
        if (v.has("berths") && v.get("berths").isArray() && !v.get("berths").isEmpty()) {
            berths = new ArrayList<>();
            for (JsonNode b : v.get("berths").values()) {
                String bid = b.asString();
                if (!rules.berths.containsKey(bid)) {
                    errors.add(where + ".berths에 없는 부두 '" + bid + "'");
                }
                berths.add(bid);
            }
        }
        if (id == null || vclass == null || biz == null || cargo == null || eta == null || grt == null || dwt == null
                || loa == null || pbl == null || draft == null || contract == null) {
            return null;
        }
        return new CaseData.Arrival(id, vessel, vclass, biz, cargo, qty == null ? 0 : qty, eta, nor, grt, dwt, loa, pbl, draft,
                contract, status, fix, berths, new CaseData.Work(hours, ratePerH, byBerth));
    }

    /** true/false 칸. 없으면 기본값, 있는데(null 포함) true/false가 아니면 오류 — "false" 같은 글자는 Python이 참으로 읽는다. */
    private boolean flag(JsonNode node, String field, String where, boolean otherwise) {
        if (!node.has(field)) {
            return otherwise;
        }
        JsonNode v = node.get(field);
        if (!v.isBoolean()) {
            errors.add(where + "는 true/false");
            return otherwise;
        }
        return v.asBoolean();
    }

    /** options.<name>이 있으면 숫자이고 [lo, hi] 안이어야 한다(integer면 정수). 엔진이 그대로 쓰는 값이라 입구에서 막는다. */
    private void optionRange(JsonNode opts, String name, double lo, double hi, boolean integer) {
        JsonNode v = opts.path(name);
        if (v.isMissingNode() || v.isNull()) {
            return;
        }
        if (!v.isNumber() || (integer && !v.isIntegralNumber()) || v.doubleValue() < lo || v.doubleValue() > hi) {
            errors.add("options." + name + "는 " + (integer ? "정수 " : "") + lo + "~" + hi + ": " + v);
        }
    }

    private static boolean absent(JsonNode v) {
        return v == null || v.isNull() || v.isMissingNode() || (v.isString() && v.asString().isBlank());
    }

    private String req(JsonNode node, String field, String where) {
        JsonNode v = node.get(field);
        if (v == null || v.isNull() || (v.isString() && v.asString().isBlank())) {
            errors.add(where + "." + field + "가 없음");
            return null;
        }
        return v.asString();
    }

    private Long time(JsonNode v, String where, boolean required) {
        if (v == null || v.isNull() || (v.isString() && v.asString().isBlank())) {
            if (required) {
                errors.add(where + "가 없음");
            }
            return null;
        }
        String s = v.asString();
        if (s.matches(".*([+-]\\d\\d:\\d\\d|Z)$")) {
            errors.add(where + ": 시간대가 붙은 값은 받지 않음 '" + s + "' (KST 현지 시각 YYYY-MM-DDTHH:MM)");
            return null;
        }
        try {
            return Times.parse(s);
        } catch (IllegalArgumentException e) {
            errors.add(where + ": " + e.getMessage());
            return null;
        }
    }

    private Double number(JsonNode v, String where, boolean required) {
        try {
            Double d = Rules.num(v);
            if (d == null && required) {
                errors.add(where + "가 없음");
            }
            if (d != null && (d.isNaN() || d.isInfinite())) {
                errors.add(where + "가 숫자가 아님");
                return null;
            }
            return d;
        } catch (RuntimeException e) {
            errors.add(where + "가 숫자가 아님");
            return null;
        }
    }
}
