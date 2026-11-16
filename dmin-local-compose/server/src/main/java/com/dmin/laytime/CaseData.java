package com.dmin.laytime;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 한 계획 기간의 입력 (= 최적화 요청 JSON). 모양은 docs/milp/ppt README 6-2절의 계약과 같다. */
public final class CaseData {

    public record Contract(long laycanFrom, long laycanTo, long laytime, long rateCents, boolean cfr, boolean weatherHalf) {}

    public record Fix(String berth, long etb, Long etu, Long workStart) {}

    public record Work(Double hours, Double ratePerH, Map<String, Double> byBerth) {}

    public record Arrival(
            String id,
            String vessel,
            String vclass,
            String biz,
            String cargo,
            double qty,
            long eta,
            Long nor,
            double grt,
            double dwt,
            double loa,
            double pbl,
            double draft,
            Contract contract,
            String status,
            Fix fix,
            List<String> berths,
            Work work) {

        /** FIX·작업 중(WORKING)은 다시 짜지 않는다. */
        public boolean movable() {
            return !"FIX".equals(status) && !"WORKING".equals(status);
        }
    }

    public record Restriction(String id, String reason, List<String> berths, long start, long end) {
        boolean on(String bid) {
            return berths.contains("*") || berths.contains(bid);
        }
    }

    public record Flow(long from, long to, double usePerH) {}

    public record Tank(String group, double opening, double minimum, double maximum, List<Flow> flows) {}

    /** 요청의 current_plan 한 줄 = 사람이 짠 현행 계획의 부두·ETB. */
    public record CurrentPlan(String berth, long etb) {}

    final String id;
    final String title;
    final long start;
    final long end;
    final Map<String, Arrival> arrivals;
    final List<Restriction> restrictions;
    final List<Tank> tanks;
    final Map<Long, long[]> sun;
    final String weatherBasis;
    final Map<String, CurrentPlan> currentPlan;

    CaseData(
            String id,
            String title,
            long start,
            long end,
            LinkedHashMap<String, Arrival> arrivals,
            List<Restriction> restrictions,
            List<Tank> tanks,
            Map<Long, long[]> sun,
            String weatherBasis,
            Map<String, CurrentPlan> currentPlan) {
        this.id = id;
        this.title = title;
        this.start = start;
        this.end = end;
        this.arrivals = arrivals;
        this.restrictions = restrictions;
        this.tanks = tanks;
        this.sun = new HashMap<>(sun);
        this.weatherBasis = weatherBasis;
        this.currentPlan = currentPlan == null ? new LinkedHashMap<>() : new LinkedHashMap<>(currentPlan);
    }

    public String id() {
        return id;
    }

    public String title() {
        return title;
    }

    public long start() {
        return start;
    }

    public long end() {
        return end;
    }

    public Map<String, Arrival> arrivals() {
        return arrivals;
    }

    public List<Restriction> restrictions() {
        return restrictions;
    }

    public List<Tank> tanks() {
        return tanks;
    }

    /** 입항 건 id → 현행 계획의 부두·ETB (입력 순서). 요청에 current_plan이 없으면 비어 있다. */
    public Map<String, CurrentPlan> currentPlan() {
        return currentPlan;
    }

    /** 그날의 (일출, 일몰). 요청에 sun이 없으면 NOAA 근사식으로 계산해 둔다 (엔진과 같다). */
    synchronized long[] sunOf(long t, Rules rules) {
        long d = Times.day0(t);
        return sun.computeIfAbsent(d, k -> Solar.riseSet(k, rules.lat, rules.lon, rules.tzHours));
    }
}
