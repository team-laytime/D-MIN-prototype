package com.dmin.laytime;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * 규칙 표 rules/terminal.json(멘토링 PPT 07~12쪽 값)을 계산에 쓰는 값으로 바꾼다. Python 엔진 pptcalc.Rules와 같은 해석이다.
 * 규칙이 바뀌면 코드가 아니라 이 표를 바꾼다. 요청 한 건에만 다른 값을 쓰려면 rule_patch를 준다.
 */
public final class Rules {

    static final ObjectMapper JSON = JsonMapper.builder().build();

    public record Berth(
            String id,
            String size,
            long direction,
            long switching,
            Double maxDwt,
            Double maxDraft,
            Double maxLoa,
            Double minLoa,
            Double minPbl,
            Set<String> groups) {}

    record PobCond(Double grtMin, Double grtMax, Set<String> biz, Double draftMin) {}

    record SunsetRow(Double grtMax, Double grtMinExclusive, double hours) {}

    record Simul(Set<String> berths, long release, Double exemptGrtLe) {}

    record Factor(String vclass, Boolean cfr, Frac factor) {}

    final String version;
    final String sha256;
    final Map<String, Berth> berths = new LinkedHashMap<>();
    final List<String> berthOrder = new ArrayList<>();
    final Set<String> productClasses;
    final Set<String> bizCodes;
    final Set<String> draftBiz;
    final Map<String, Double> minDwt = new LinkedHashMap<>(); // 부두별 최소 DWT (Buoy 등). 비어 있으면 비교하지 않음
    final List<PobCond> pobSubject = new ArrayList<>();
    final List<SunsetRow> pobSunset = new ArrayList<>();
    final String pobCompare;
    final long pobRelease;
    final double dawnGrtMin;
    final boolean dawnSubjectOnly; // dawn.scope = SUBJECT(팀원 코드)면 야간 도선 대상 선박에만 새벽 02~08시 금지
    final long dawnFrom;
    final long dawnTo;
    final boolean fixStrict;
    final List<Set<String>> cargoSets = new ArrayList<>();
    final long cargoRelease;
    final List<Simul> simul = new ArrayList<>();
    final String restrictionScope;
    final long setup;
    final long hose;
    final long departure;
    final Set<String> daylight;
    final long notice;
    final long earlyHour;
    final long earlyHourDaylight;
    final long dayHour;
    final List<Factor> factors = new ArrayList<>();
    final Frac wxRatio;
    final String wxBasis;
    final double lat;
    final double lon;
    final double tzHours;

    private Rules(JsonNode raw, String sha256) {
        this.sha256 = sha256;
        this.version = raw.get("version").asString();
        for (JsonNode b : raw.get("berths").values()) {
            Set<String> groups = new LinkedHashSet<>(b.path("groups").propertyNames());
            Berth berth = new Berth(
                    b.get("id").asString(),
                    text(b.get("size")),
                    Times.mins(b.get("direction_h").asDouble()),
                    Times.mins(b.get("switching_h").asDouble()),
                    num(b.get("max_dwt")),
                    num(b.get("max_draft")),
                    num(b.get("max_loa")),
                    num(b.get("min_loa")),
                    num(b.get("min_pbl")),
                    groups);
            berths.put(berth.id(), berth);
            berthOrder.add(berth.id());
        }
        this.productClasses = new LinkedHashSet<>(raw.path("product_classes").propertyNames());
        this.bizCodes = new LinkedHashSet<>(raw.path("biz").propertyNames());
        this.draftBiz = strings(raw.get("eligibility").get("draft_check_biz"));
        JsonNode md = raw.get("eligibility").get("min_dwt_by_berth");
        if (md != null && md.isObject()) {
            for (String bid : md.propertyNames()) {
                Double v = num(md.get(bid));
                if (v != null) {
                    minDwt.put(bid, v);
                }
            }
        }
        JsonNode np = raw.get("night_pilotage");
        JsonNode pob = np.get("last_pob");
        for (JsonNode c : pob.get("subject_any").values()) {
            pobSubject.add(new PobCond(
                    num(c.get("grt_min")),
                    num(c.get("grt_max")),
                    c.has("biz") ? strings(c.get("biz")) : null,
                    num(c.get("draft_min"))));
        }
        for (JsonNode r : pob.get("sunset_minus_h").values()) {
            pobSunset.add(new SunsetRow(num(r.get("grt_max")), num(r.get("grt_min_exclusive")), r.get("h").asDouble()));
        }
        this.pobCompare = pob.get("compare").asString();
        this.pobRelease = Times.hm(pob.get("release").asString());
        JsonNode dawn = np.get("dawn");
        this.dawnGrtMin = dawn.get("grt_min").asDouble();
        String scope = dawn.has("scope") ? dawn.get("scope").asString() : "GRT";
        if (!scope.equals("GRT") && !scope.equals("SUBJECT")) {
            throw new IllegalArgumentException("night_pilotage.dawn.scope는 GRT·SUBJECT 중 하나: " + scope);
        }
        this.dawnSubjectOnly = scope.equals("SUBJECT");
        this.dawnFrom = Times.hm(dawn.get("from").asString());
        this.dawnTo = Times.hm(dawn.get("to").asString());
        JsonNode pr = raw.get("pair_rules");
        this.fixStrict = pr.get("same_berth").get("fix_strict").asBoolean();
        for (JsonNode s : pr.get("same_cargo_group").get("berth_sets").values()) {
            cargoSets.add(strings(s));
        }
        this.cargoRelease = Times.mins(pr.get("same_cargo_group").get("release_before_etu_h").asDouble());
        for (JsonNode s : pr.get("simultaneous").values()) {
            simul.add(new Simul(
                    strings(s.get("berths")),
                    Times.mins(s.get("release_before_etu_h").asDouble()),
                    num(s.get("exempt_if_all_grt_le"))));
        }
        this.restrictionScope = raw.get("restriction").get("scope").asString();
        JsonNode w = raw.get("work");
        this.setup = Times.mins(w.get("setup_h").asDouble());
        this.hose = Times.mins(w.get("hose_h").asDouble());
        this.departure = Times.mins(w.get("departure_h").asDouble());
        JsonNode lt = raw.get("laytime");
        this.daylight = strings(lt.get("daylight_classes"));
        this.notice = Times.mins(lt.get("notice_h").asDouble());
        this.earlyHour = (long) (lt.get("before_laycan_hour").asDouble() * 60);
        this.earlyHourDaylight = (long) (lt.get("before_laycan_hour_daylight").asDouble() * 60);
        this.dayHour = (long) (lt.get("daylight_hour").asDouble() * 60);
        for (JsonNode f : lt.get("factor").values()) {
            factors.add(new Factor(
                    f.has("class") ? f.get("class").asString() : null,
                    f.has("cfr") ? f.get("cfr").asBoolean() : null,
                    frac(f.get("factor"))));
        }
        JsonNode dm = raw.get("demurrage");
        this.wxRatio = frac(dm.get("weather_ratio"));
        this.wxBasis = dm.get("weather_basis").asString();
        JsonNode loc = raw.get("location");
        this.lat = loc.get("lat").asDouble();
        this.lon = loc.get("lon").asDouble();
        this.tzHours = loc.get("tz_hours").asDouble();
    }

    /** 이미지에 넣은 규칙 표 (src/main/resources/rules/terminal.json). Python 에이전트의 표와 같은 파일이어야 한다. */
    public static Rules bundled() {
        return bundled(Map.of());
    }

    public static Rules bundled(Map<String, ?> patch) {
        try (InputStream in = Rules.class.getResourceAsStream("/rules/terminal.json")) {
            if (in == null) {
                throw new IllegalStateException("rules/terminal.json 없음");
            }
            byte[] bytes = in.readAllBytes();
            return of(new String(bytes, StandardCharsets.UTF_8), patch);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    /** 규칙 표에 들어 있는 해석 묶음 이름 (profiles의 '_'로 시작하지 않는 키). 'ppt' = 표 그대로, 'team' = 팀원 코드 해석. */
    public static List<String> profileNames() {
        List<String> out = new ArrayList<>();
        for (String k : bundledRaw().path("profiles").propertyNames()) {
            if (!k.startsWith("_")) {
                out.add(k);
            }
        }
        return out;
    }

    /** 해석 묶음의 제목 (화면·요약용). 없는 이름이면 IllegalArgumentException. */
    public static String profileTitle(String name) {
        return profile(name).path("title").asString(name);
    }

    /**
     * 데이터의 rule_patch 위에 해석 묶음의 patch를 덮어쓴다 (Python pptcalc.profile_patch와 같다).
     * 같은 경로가 둘 다 있으면 해석 묶음 값이 이긴다 — 실행할 때 고른 해석이 데이터보다 앞선다.
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> profilePatch(String name, Map<String, ?> base) {
        Map<String, Object> out = new LinkedHashMap<>();
        if (base != null) {
            out.putAll(base);
        }
        out.putAll(JSON.treeToValue(profile(name).path("patch"), Map.class));
        return out;
    }

    private static JsonNode profile(String name) {
        JsonNode p = name == null || name.startsWith("_") ? null : bundledRaw().path("profiles").get(name);
        if (p == null || !p.isObject()) {
            throw new IllegalArgumentException("없는 규칙 해석: " + name + " (있는 것: " + profileNames() + ")");
        }
        return p;
    }

    private static JsonNode bundledRaw() {
        try (InputStream in = Rules.class.getResourceAsStream("/rules/terminal.json")) {
            if (in == null) {
                throw new IllegalStateException("rules/terminal.json 없음");
            }
            return JSON.readTree(new String(in.readAllBytes(), StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    public static Rules of(String json, Map<String, ?> patch) {
        JsonNode raw = JSON.readTree(json);
        if (patch != null && !patch.isEmpty()) {
            raw = applyPatch(raw.deepCopy(), patch);
        }
        return new Rules(raw, sha256(json));
    }

    /**
     * "demurrage.weather_basis": "WAIT" 꼴 경로로 값을 바꾼다 (Python Rules(patch=...)와 같다).
     * 이미 있는 값만 바꾼다: 경로의 키가 표에 없거나 배열 번호가 범위 밖이면 오류다(오타로 새 키가 생겨 아무것도 안 바뀌는 일을 막는다).
     */
    static JsonNode applyPatch(JsonNode root, Map<String, ?> patch) {
        for (Map.Entry<String, ?> e : patch.entrySet()) {
            String[] keys = e.getKey().split("\\.");
            JsonNode node = root;
            for (int i = 0; i < keys.length - 1; i++) {
                node = child(node, keys[i], e.getKey());
            }
            JsonNode value = JSON.valueToTree(e.getValue());
            String last = keys[keys.length - 1];
            if (!(node instanceof ArrayNode) && !(node instanceof ObjectNode)) {
                throw new IllegalArgumentException("rule_patch 경로가 값에서 끝남: " + e.getKey());
            }
            child(node, last, e.getKey()); // 마지막 키도 이미 있어야 한다
            if (node instanceof ArrayNode arr) {
                arr.set(Integer.parseInt(last), value);
            } else {
                ((ObjectNode) node).set(last, value);
            }
        }
        return root;
    }

    /** 경로 한 칸. 객체면 이미 있는 키, 배열이면 0 ~ 크기−1 번호만 받는다. */
    private static JsonNode child(JsonNode node, String key, String path) {
        if (node instanceof ArrayNode arr) {
            int i;
            try {
                i = Integer.parseInt(key);
            } catch (NumberFormatException ex) {
                i = -1;
            }
            if (i >= 0 && i < arr.size()) {
                return arr.get(i);
            }
        } else if (node instanceof ObjectNode obj && obj.has(key)) {
            return obj.get(key);
        }
        throw new IllegalArgumentException("rule_patch 경로 없음: " + path);
    }

    public String version() {
        return version;
    }

    /** 기상체선을 세는 구간 (USED · DEMURRAGE · WAIT). 데이터의 options.weather_basis가 있으면 그쪽이 쓰인다(CaseParser). */
    public String weatherBasis() {
        return wxBasis;
    }

    /** 규칙 표 원문의 지문. 에이전트가 같은 표로 풀었는지 확인할 때 쓴다. */
    public String sha256() {
        return sha256;
    }

    public Map<String, Berth> berths() {
        return berths;
    }

    public List<String> berthOrder() {
        return berthOrder;
    }

    public Set<String> productClasses() {
        return productClasses;
    }

    public Set<String> bizCodes() {
        return bizCodes;
    }

    static Double num(JsonNode n) {
        if (n == null || n.isNull() || n.isMissingNode()) {
            return null;
        }
        if (n.isNumber()) {
            return n.doubleValue();
        }
        if (n.isString()) {
            String s = n.asString().strip();
            return s.isEmpty() ? null : Double.parseDouble(s);
        }
        throw new IllegalArgumentException("숫자가 아님: " + n);
    }

    static String text(JsonNode n) {
        return n == null || n.isNull() || n.isMissingNode() ? null : n.asString();
    }

    static Set<String> strings(JsonNode arr) {
        Set<String> out = new LinkedHashSet<>();
        if (arr != null) {
            for (JsonNode v : arr.values()) {
                out.add(v.asString());
            }
        }
        return out;
    }

    static Frac frac(JsonNode n) {
        return n.isString() ? Frac.parse(n.asString()) : Frac.fromDouble(n.doubleValue());
    }

    static String sha256(String text) {
        try {
            byte[] h = MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(h);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
