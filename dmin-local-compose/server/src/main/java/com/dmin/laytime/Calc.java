package com.dmin.laytime;

import static com.dmin.laytime.Times.DAY;
import static com.dmin.laytime.Times.day0;
import static com.dmin.laytime.Times.fmt;
import static com.dmin.laytime.Times.mins;

import com.dmin.laytime.CaseData.Arrival;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/**
 * 멘토링 PPT 06~12쪽 계산식 P1~P22의 Java판 (규칙 평가 엔진, 정의서 CMP-07). 프레임워크에 기대지 않는다.
 * Python 엔진(docs/milp/ppt/pptcalc.py·planner.py)과 같은 입력이면 같은 시각·같은 센트가 나와야 한다 — GoldenCrossCheckTest가 지킨다.
 *
 * <pre>
 * P1  배정 가능 부두          P4 야간 도선 금지 구간      P5 부두 제약 금지 구간     P7 ETB = 금지 구간을 피한 가장 이른 시각
 * P9  작업시작 = ETB + 1h     P10 작업완료 = 작업시작 + 물량 ÷ 평균 Rate         P11 호스분리 = 작업완료 + 30분
 * P12 이안 = 작업완료 + 2h    P13 ETANR = NVL(NOR, ETA)   P14·P15 정박개시          P16 정박종료 = 정박개시 + Laytime × 배수
 * P17 기상체선 공제 ½         P18 체선시간 = max(0, 호스분리 − 정박종료 − 공제)  P19 체선료 = 체선시간 × Rate ÷ 24
 * P3·P6·P8 두 작업계획 사이 충돌                         P22 원유 탱크 재고
 * </pre>
 */
public final class Calc {

    public record Window(long from, long to, String tag) {}

    private Calc() {}

    // ------------------------------------------------------------------ P1 배정 가능 부두
    /** 제품 그룹을 받고 제원 5종이 맞는 부두인가. 맞으면 빈 목록, 아니면 사유. 비어 있는 제원은 비교하지 않고 Draft는 수입선만 본다. */
    public static List<String> ineligible(Rules rules, Arrival a, String bid) {
        Rules.Berth b = rules.berths.get(bid);
        List<String> bad = new ArrayList<>();
        if (b == null) {
            bad.add("없는 부두 " + bid);
            return bad;
        }
        if (!b.groups().contains(a.cargo())) {
            bad.add("제품 그룹 " + a.cargo() + " 미취급");
        }
        if (b.maxDwt() != null && a.dwt() > b.maxDwt()) {
            bad.add(String.format("DWT %,.0f > 최대 %,.0f", a.dwt(), b.maxDwt()));
        }
        Double minDwt = rules.minDwt.get(bid);
        if (minDwt != null && a.dwt() < minDwt) {
            bad.add(String.format("DWT %,.0f < 최소 %,.0f", a.dwt(), minDwt));
        }
        if (b.maxLoa() != null && a.loa() > b.maxLoa()) {
            bad.add("LOA " + a.loa() + " > 최대 " + b.maxLoa());
        }
        if (b.minLoa() != null && a.loa() < b.minLoa()) {
            bad.add("LOA " + a.loa() + " < 최소 " + b.minLoa());
        }
        if (b.minPbl() != null && a.pbl() < b.minPbl()) {
            bad.add("PBL " + a.pbl() + " < 최소 " + b.minPbl());
        }
        if (rules.draftBiz.contains(a.biz()) && b.maxDraft() != null && a.draft() > b.maxDraft()) {
            bad.add("Draft " + a.draft() + " > 최대 " + b.maxDraft());
        }
        return bad;
    }

    public static List<String> eligibleBerths(Rules rules, Arrival a) {
        if (!a.movable()) {
            return List.of(a.fix().berth());
        }
        List<String> pool = a.berths() == null || a.berths().isEmpty() ? rules.berthOrder : a.berths();
        return pool.stream().filter(bid -> ineligible(rules, a, bid).isEmpty()).toList();
    }

    // ------------------------------------------------------------------ P2 · P4 · P5 · P7 접안 가능 시각
    /** P2: 빈 부두에 대는 가장 이른 시각 = ETA + Direction */
    public static long tau0(Rules rules, Arrival a, String bid) {
        return a.eta() + rules.berths.get(bid).direction();
    }

    static boolean pobSubject(Rules rules, Arrival a) {
        for (Rules.PobCond c : rules.pobSubject) {
            if (c.grtMin() != null && a.grt() < c.grtMin()) {
                continue;
            }
            if (c.grtMax() != null && a.grt() > c.grtMax()) {
                continue;
            }
            if (c.biz() != null && !c.biz().contains(a.biz())) {
                continue;
            }
            if (c.draftMin() != null && a.draft() < c.draftMin()) {
                continue;
            }
            return true;
        }
        return false;
    }

    static Long lastPob(Rules rules, CaseData cs, Arrival a, long dayStart) {
        long sunset = cs.sunOf(dayStart, rules)[1];
        for (Rules.SunsetRow row : rules.pobSunset) {
            if (row.grtMax() != null && a.grt() > row.grtMax()) {
                continue;
            }
            if (row.grtMinExclusive() != null && a.grt() <= row.grtMinExclusive()) {
                continue;
            }
            return sunset - mins(row.hours());
        }
        return null;
    }

    /** P4 (PPT 08쪽 ②): 이 선박이 접안할 수 없는 야간 구간 [시작, 끝) */
    static List<Window> nightWindows(Rules rules, CaseData cs, Arrival a) {
        List<Window> out = new ArrayList<>();
        long rel = rules.pobRelease;
        boolean subject = pobSubject(rules, a);
        if (subject) {
            if ("ETA".equals(rules.pobCompare) || "ETA_DAY".equals(rules.pobCompare)) {
                long d = day0(a.eta());
                if ("ETA".equals(rules.pobCompare) && a.eta() < d + rel) { // 자정~08시 도착 = 전날 Last POB 뒤 (ETA_DAY는 그 날짜만 본다)
                    out.add(new Window(a.eta(), d + rel, "Last POB 뒤 도착"));
                } else {
                    Long pob = lastPob(rules, cs, a, d);
                    if (pob != null && a.eta() >= pob) {
                        out.add(new Window(a.eta(), d + DAY + rel, "Last POB 뒤 도착"));
                    }
                }
            } else {
                for (long d = day0(cs.start) - DAY; d <= cs.end; d += DAY) {
                    Long pob = lastPob(rules, cs, a, d);
                    if (pob != null) {
                        out.add(new Window(pob, d + DAY + rel, "Last POB ~ 08시"));
                    }
                }
            }
        }
        if ((subject || !rules.dawnSubjectOnly) && a.grt() >= rules.dawnGrtMin) { // SUBJECT(팀원 코드)면 대상 선박에만
            for (long d = day0(Math.min(a.eta(), cs.start)) - DAY; d <= cs.end + DAY; d += DAY) {
                out.add(new Window(d + rules.dawnFrom, d + rules.dawnTo, "새벽 02~08시"));
            }
        }
        return out;
    }

    /** P5 (PPT 08쪽 ③-1): 부두 제약 → [시작, 종료 + Direction)에는 접안하지 못한다. */
    static List<Window> restrictionWindows(Rules rules, CaseData cs, Arrival a, String bid, long stay) {
        Rules.Berth b = rules.berths.get(bid);
        long lead = "STAY".equals(rules.restrictionScope) ? stay : 0;
        List<Window> out = new ArrayList<>();
        for (CaseData.Restriction r : cs.restrictions) {
            if (r.on(bid)) {
                out.add(new Window(r.start() - lead, r.end() + b.direction(), "부두 제약 " + r.id()));
            }
        }
        return out;
    }

    static List<Window> merge(List<Window> windows) {
        List<Window> sorted = new ArrayList<>(windows);
        sorted.sort(Comparator.comparingLong(Window::from).thenComparingLong(Window::to).thenComparing(Window::tag));
        List<Window> out = new ArrayList<>();
        for (Window w : sorted) {
            if (w.to() <= w.from()) {
                continue;
            }
            if (!out.isEmpty() && w.from() <= out.getLast().to()) {
                if (w.to() > out.getLast().to()) {
                    out.set(out.size() - 1, new Window(out.getLast().from(), w.to(), w.tag()));
                }
            } else {
                out.add(w);
            }
        }
        return out;
    }

    /** P7 (PPT 06쪽): 모든 금지 구간을 함께 피한 가장 이른 시각. 금지 구간 안이면 그 끝, 아니면 그대로. */
    static Window phi(List<Window> merged, long tau) {
        for (Window w : merged) {
            if (w.from() <= tau && tau < w.to()) {
                return new Window(w.to(), w.to(), w.tag());
            }
            if (w.from() > tau) {
                break;
            }
        }
        return new Window(tau, tau, null);
    }

    static List<Window> windowsOf(Rules rules, CaseData cs, Arrival a, String bid) {
        List<Window> all = new ArrayList<>(nightWindows(rules, cs, a));
        all.addAll(restrictionWindows(rules, cs, a, bid, stayMinutes(rules, a, bid)));
        all.add(new Window(-1_000_000_000L, cs.start, "계획 시작 전"));
        return merge(all);
    }

    // ------------------------------------------------------------------ P9~P12 작업 시각
    /** P10: 작업시간 = 물량 ÷ 평균 Rate (과거 Shipment에서 구해 입력으로 준다). */
    static long workMinutes(Arrival a, String bid) {
        CaseData.Work w = a.work();
        if (w.hours() != null) {
            return mins(w.hours());
        }
        Double rate = w.byBerth() != null && w.byBerth().containsKey(bid) ? w.byBerth().get(bid) : w.ratePerH();
        if (rate == null || rate == 0) {
            throw new IllegalArgumentException(a.id() + ": 작업시간도 평균 Rate도 없다");
        }
        return (long) Math.ceil(a.qty() / rate * 60);
    }

    static long stayMinutes(Rules rules, Arrival a, String bid) {
        return rules.setup + workMinutes(a, bid) + rules.departure;
    }

    // ------------------------------------------------------------------ P13~P15 정박개시
    record LayStart(long t, String rule, String text) {}

    static LayStart laytimeStart(Rules rules, CaseData cs, Arrival a, long s) {
        CaseData.Contract c = a.contract();
        long etanr = a.nor() != null ? a.nor() : a.eta(); // P13
        boolean dl = rules.daylight.contains(a.vclass());
        String page = dl ? "10쪽" : "09쪽";
        if (etanr < c.laycanFrom() && s < c.laycanFrom()) {
            return new LayStart(s, "Early Loading", "ETANR·ETB 모두 LayCan From 전 → 정박개시 = ETB (" + page + ")");
        }
        if (etanr > c.laycanTo()) {
            return new LayStart(s, "LayCan Miss", "ETANR이 LayCan To 뒤 → 정박개시 = ETB (" + page + ")");
        }
        if (etanr < c.laycanFrom()) {
            long t = day0(c.laycanFrom()) + (dl ? rules.earlyHourDaylight : rules.earlyHour);
            return new LayStart(t, "조기 도착", "ETANR이 LayCan From 전 → LayCan From의 오전 " + (dl ? "07" : "06") + "시 (" + page + ")");
        }
        long base;
        String name;
        if (!dl) {
            base = etanr + rules.notice;
            name = "ETANR + 6h";
        } else {
            long[] sun = cs.sunOf(etanr, rules);
            if (sun[0] < etanr && etanr < sun[1]) {
                base = etanr + rules.notice;
                name = "일출~일몰 사이 → ETANR + 6h";
            } else if (etanr <= sun[0]) {
                base = day0(etanr) + rules.dayHour;
                name = "일출 전 → ETANR 날의 07시";
            } else {
                base = day0(etanr) + DAY + rules.dayHour;
                name = "일몰 뒤 → ETANR 다음 날의 07시";
            }
        }
        if (s < base) {
            return new LayStart(s, "ETB가 더 이름", name + " = " + fmt(base) + "보다 ETB가 이름 → 정박개시 = ETB (" + page + ")");
        }
        return new LayStart(base, dl ? "Daylight" : "LayCan 안", name + " (" + page + ")");
    }

    /** P16 (PPT 10쪽): '원유 && CFR False'이면 LayTime ÷ 2 */
    static Frac laytimeFactor(Rules rules, Arrival a) {
        for (Rules.Factor f : rules.factors) {
            boolean classOk = f.vclass() == null || f.vclass().equals(a.vclass());
            boolean cfrOk = f.cfr() == null || f.cfr() == a.contract().cfr();
            if (classOk && cfrOk) {
                return f.factor();
            }
        }
        return Frac.ONE;
    }

    static List<long[]> weatherWindows(CaseData cs, String bid) {
        List<long[]> spans = new ArrayList<>();
        for (CaseData.Restriction r : cs.restrictions) {
            if ("WEATHER".equals(r.reason()) && r.on(bid)) {
                spans.add(new long[] {r.start(), r.end()});
            }
        }
        spans.sort(Comparator.<long[]>comparingLong(x -> x[0]).thenComparingLong(x -> x[1]));
        List<long[]> out = new ArrayList<>();
        for (long[] w : spans) {
            if (!out.isEmpty() && w[0] <= out.getLast()[1]) {
                out.getLast()[1] = Math.max(out.getLast()[1], w[1]);
            } else {
                out.add(new long[] {w[0], w[1]});
            }
        }
        return out;
    }

    static Frac overlap(Frac a0, Frac a1, Frac b0, Frac b1) {
        return Frac.max(Frac.ZERO, Frac.min(a1, b1).sub(Frac.max(a0, b0)));
    }

    // ------------------------------------------------------------------ P9~P19 작업계획 하나
    /** 접안 시각 s가 정해진 작업계획 하나를 끝까지 계산한다. fixed면 입력의 작업시작·이안 시각을 쓴다(FIX·작업 중). */
    public static Plan makePlan(Rules rules, CaseData cs, Arrival a, String bid, long s, boolean fixed) {
        CaseData.Fix fx = a.fix();
        Long ws = fixed && fx != null ? fx.workStart() : null;
        Long etu = fixed && fx != null ? fx.etu() : null;
        long st = ws != null ? ws : s + rules.setup; // P9
        long c = etu != null ? etu - rules.departure : st + workMinutes(a, bid); // P10
        long h = c + rules.hose; // P11
        long u = c + rules.departure; // P12
        LayStart ls = laytimeStart(rules, cs, a, s); // P13~P15
        Frac lam = laytimeFactor(rules, a);
        Frac allowed = Frac.of(a.contract().laytime()).mul(lam); // P16
        Frac le = allowed.add(ls.t());
        Frac dtRaw = Frac.of(h).sub(le); // P18 앞부분
        Frac lo;
        Frac hi;
        switch (cs.weatherBasis) {
            case "DEMURRAGE" -> {
                lo = le;
                hi = Frac.of(h);
            }
            case "WAIT" -> {
                lo = Frac.of(ls.t());
                hi = Frac.of(s);
            }
            default -> {
                lo = Frac.of(ls.t());
                hi = Frac.of(h);
            }
        }
        Frac ratio = a.contract().weatherHalf() ? rules.wxRatio : Frac.ZERO;
        Frac wx = Frac.ZERO;
        if (dtRaw.signum() > 0) {
            for (long[] w : weatherWindows(cs, bid)) {
                wx = wx.add(overlap(Frac.of(w[0]), Frac.of(w[1]), lo, hi));
            }
        }
        Frac ded = wx.mul(ratio); // P17
        Frac dt = Frac.max(Frac.ZERO, dtRaw.sub(ded)); // P18
        long cents = dt.mul(a.contract().rateCents()).div(DAY).floorHalfUp(); // P19
        return new Plan(a.id(), bid, s, st, c, h, u, ls.t(), ls.rule(), ls.text(), allowed, le, dtRaw, wx, ded, dt, cents, fixed);
    }

    // 산출 근거(trace) 문장은 Python 응답의 plans[].trace에 있다. Spring은 문장을 만들지 않고 숫자만 다시 계산해 맞춰 본다.

    // ------------------------------------------------------------------ P3 · P6 · P8 두 작업계획 사이
    record Relation(String kind, long minutes) {}

    static Relation relation(Rules rules, Arrival a1, String b1, Arrival a2, String b2) {
        if (b1.equals(b2)) {
            return new Relation("같은 부두", rules.berths.get(b1).switching()); // P3
        }
        for (var bs : rules.cargoSets) { // P6 동일 화물 그룹
            if (bs.contains(b1) && bs.contains(b2) && a1.cargo().equals(a2.cargo())) {
                return new Relation("동일 화물 그룹", rules.cargoRelease);
            }
        }
        for (Rules.Simul sm : rules.simul) { // P6 부두 동시 접안
            boolean exempt = sm.exemptGrtLe() != null && a1.grt() <= sm.exemptGrtLe() && a2.grt() <= sm.exemptGrtLe();
            if (sm.berths().contains(b1) && sm.berths().contains(b2) && !exempt) {
                return new Relation("부두 동시 접안", sm.release());
            }
        }
        return null;
    }

    /** 두 작업계획을 같이 고를 수 없는가 → 이유 또는 null. 뒤에 서는 쪽이 FIX면 같은 시각도 불가(PPT 07쪽 '접안불가'). */
    static String conflict(Rules rules, CaseData cs, Plan p, Plan q) {
        Relation rel = relation(rules, cs.arrivals.get(p.aid()), p.berth(), cs.arrivals.get(q.aid()), q.berth());
        if (rel == null) {
            return null;
        }
        long v = rel.minutes();
        boolean qAfter;
        boolean pAfter;
        if ("같은 부두".equals(rel.kind())) {
            qAfter = rules.fixStrict && q.fixed() && !p.fixed() ? q.s() > p.u() + v : q.s() >= p.u() + v;
            pAfter = rules.fixStrict && p.fixed() && !q.fixed() ? p.s() > q.u() + v : p.s() >= q.u() + v;
        } else {
            qAfter = q.s() >= p.u() - v;
            pAfter = p.s() >= q.u() - v;
        }
        return qAfter || pAfter ? null : rel.kind();
    }

    // ------------------------------------------------------------------ P22 재고
    private static final Map<String, Integer> INFLOW = Map.of("IM", 1, "DI", 1, "EX", -1, "DO", -1);

    static List<String> tankViolations(CaseData cs, List<Plan> plans) {
        List<String> out = new ArrayList<>();
        for (CaseData.Tank tank : cs.tanks) {
            List<double[]> mine = new ArrayList<>(); // [시간당 물량, 작업시작, 작업완료]
            for (Plan p : plans) {
                Arrival a = cs.arrivals.get(p.aid());
                if (a.cargo().equals(tank.group())) {
                    long dur = p.c() - p.a();
                    double rate = dur > 0 ? INFLOW.get(a.biz()) * a.qty() / dur * 60 : 0.0;
                    mine.add(new double[] {rate, p.a(), p.c()});
                }
            }
            TreeSet<Long> pts = new TreeSet<>(List.of(cs.start, cs.end));
            for (double[] m : mine) {
                for (double t : new double[] {m[1], m[2]}) {
                    if (cs.start < t && t < cs.end) {
                        pts.add((long) t);
                    }
                }
            }
            for (CaseData.Flow f : tank.flows()) {
                for (long t : new long[] {f.from(), f.to()}) {
                    if (cs.start < t && t < cs.end) {
                        pts.add(t);
                    }
                }
            }
            List<Long> ps = new ArrayList<>(pts);
            double level = tank.opening();
            String bad = check(tank, ps.getFirst(), level);
            for (int i = 0; bad == null && i + 1 < ps.size(); i++) {
                long t0 = ps.get(i);
                long t1 = ps.get(i + 1);
                double in = 0;
                for (double[] m : mine) {
                    in += m[0] * Math.max(0, Math.min(m[2], t1) - Math.max(m[1], t0)) / 60;
                }
                level += in;
                double use = 0;
                for (CaseData.Flow f : tank.flows()) {
                    use += f.usePerH() * Math.max(0, Math.min(f.to(), t1) - Math.max(f.from(), t0)) / 60;
                }
                level -= use;
                bad = check(tank, t1, level);
            }
            if (bad != null) {
                out.add(bad);
            }
        }
        return out;
    }

    private static String check(CaseData.Tank tank, long t, double level) {
        double eps = 1e-6;
        if (level > tank.maximum() + eps) {
            return String.format("%s 재고 %,.0f > 저장용량 %,.0f (%s)", tank.group(), level, tank.maximum(), fmt(t));
        }
        if (level < tank.minimum() - eps) {
            return String.format("%s 재고 %,.0f < 최소 허용 재고 %,.0f (%s)", tank.group(), level, tank.minimum(), fmt(t));
        }
        return null;
    }
}
