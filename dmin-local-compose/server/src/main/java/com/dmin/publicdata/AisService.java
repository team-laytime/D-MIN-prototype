package com.dmin.publicdata;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import org.springframework.stereotype.Service;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

/**
 * 울산항만공사 항내 선박위치정보(15156631)·항만 내 선박 운항정보(15156628). demo/src/demurrage/data/ais.py를 Spring으로 옮긴 것이다.
 * - 위치는 30초 동안 모아 쓴다(원본이 약 5분 주기 일괄 갱신이라 더 짧게 해도 소용없다, demo/docs/16 #12).
 *   한 쪽 1,000척씩 totalCount만큼 받는다(최대 5쪽). 5,000척을 넘으면 일부만 보여 주지 않고 오류로 둔다.
 * - 운항 기록은 호출부호·연도마다 5분 캐시(최근에 본 256척까지).
 * - 실패하면 마지막 성공값을 stale로 내려 준다. 처음부터 실패하면 예외(→ 503).
 * - 이 API에는 목적지·ETA·DWT가 없다. ETA는 입항 신고(EntryService)에서 온다.
 */
@Service
public class AisService {

    static final String POSITION = "/B551938/VslPstnInfoService/getVslPstnInfo";
    static final String VOYAGE = "/B551938/VslNvgtInfoService/getVtsBaseVslNvgtInfo";
    static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private static final DateTimeFormatter COMPACT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");
    /** 초까지 늘 쓴다 (Python isoformat과 같은 모양: 2026-11-12T17:06:00+09:00). */
    static final DateTimeFormatter OUT = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ssXXX");
    static final int POSITION_PAGE = 1000;
    static final int POSITION_MAX_PAGES = 5;
    static final int VOYAGE_CACHE_MAX = 256;

    private final PublicDataClient client;
    private final PublicDataProperties props;
    private final ObjectMapper json;
    private final Clock clock;

    private List<JsonNode> rows;
    private Instant rowsAt = Instant.EPOCH;
    private String fetchedAt;
    /** 최근에 본 순서(access order). 256척을 넘으면 가장 오래 안 본 것부터 버린다. synchronized(voyages)로만 만진다. */
    private final Map<String, CachedVoyage> voyages = new LinkedHashMap<>(16, 0.75f, true) {
        @Override
        protected boolean removeEldestEntry(Map.Entry<String, CachedVoyage> eldest) {
            return size() > VOYAGE_CACHE_MAX;
        }
    };

    private record CachedVoyage(Instant at, List<Map<String, Object>> events) {}

    AisService(PublicDataClient client, PublicDataProperties props, ObjectMapper json, Clock clock) {
        this.client = client;
        this.props = props;
        this.json = json;
        this.clock = clock;
    }

    public Map<String, Object> vessels(double maxAgeMin, double[] bbox) {
        boolean stale = false;
        String error = null;
        List<JsonNode> raw;
        String fetched;
        synchronized (this) {
            if (rows == null || clock.instant().isAfter(rowsAt.plus(props.aisCache()))) {
                try {
                    rows = fetchPositions();
                    rowsAt = clock.instant();
                    fetchedAt = OffsetDateTime.now(clock).format(OUT);
                } catch (PublicDataException e) {
                    if (rows == null) {
                        throw e;
                    }
                    stale = true;
                    error = e.getMessage();
                }
            }
            raw = rows;
            fetched = fetchedAt;
        }
        OffsetDateTime now = OffsetDateTime.now(clock);
        List<Map<String, Object>> all = new ArrayList<>();
        for (JsonNode r : raw) {
            Map<String, Object> v = normalize(r, now);
            if (v != null) {
                all.add(v);
            }
        }
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> v : all) {
            Double age = (Double) v.get("ageMin");
            if (age == null || age > maxAgeMin) {
                continue;
            }
            double lat = (Double) v.get("lat");
            double lng = (Double) v.get("lng");
            if (bbox != null && !(bbox[0] <= lat && lat <= bbox[2] && bbox[1] <= lng && lng <= bbox[3])) {
                continue;
            }
            out.add(v);
        }
        out.sort(Comparator.comparingDouble(v -> (Double) v.get("ageMin")));
        Map<String, Object> doc = new LinkedHashMap<>();
        doc.put("source", "울산항만공사 항내 선박위치정보 (공공데이터포털 15156631)");
        doc.put("fetchedAt", fetched);
        doc.put("stale", stale);
        doc.put("total", all.size());
        doc.put("count", out.size());
        doc.put("maxAgeMin", maxAgeMin);
        doc.put("vessels", out);
        if (error != null) {
            doc.put("error", error);
        }
        return doc;
    }

    /** API 한 줄 → 화면용 한 줄. 위치가 없으면 null. 필드 이름은 화면(src/lib/liveAis.js)이 쓰는 그대로다. */
    static Map<String, Object> normalize(JsonNode r, OffsetDateTime now) {
        Double lat = num(r.get("lat"));
        Double lng = num(r.get("lot"));
        if (lat == null || lng == null) {
            return null;
        }
        OffsetDateTime upd = compact(text(r.get("updtTm")));
        Double draft = num(r.get("drft"));
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("mmsi", text(r.get("mmsiNo")));
        v.put("imo", text(r.get("imoNo")));
        v.put("callSign", text(r.get("callsgn")));
        String name = text(r.get("vslNm"));
        v.put("name", name == null ? "" : name.strip());
        v.put("lat", lat);
        v.put("lng", lng);
        v.put("sog", num(r.get("sog")));
        v.put("cog", integer(r.get("cog")));
        v.put("heading", integer(r.get("hdgAng")));
        v.put("rot", num(r.get("rot")));
        v.put("draft", draft == null || draft == 0 ? null : draft);
        v.put("navStatus", text(r.get("nvgtStts")));
        v.put("callYear", text(r.get("ptentYr")));
        v.put("voyage", text(r.get("vyg")));
        v.put("updatedAt", upd == null ? null : upd.format(OUT));
        v.put("ageMin", upd == null ? null : Math.round((now.toEpochSecond() - upd.toEpochSecond()) / 60.0 * 10) / 10.0);
        return v;
    }

    /** 1쪽부터 받은 수가 totalCount에 닿을 때까지(최대 5쪽). totalCount가 없으면 1쪽만 받는다. */
    private List<JsonNode> fetchPositions() {
        List<JsonNode> out = new ArrayList<>();
        for (int page = 1; ; page++) {
            byte[] body = client.get(POSITION, Map.of(
                    "pageNo", Integer.toString(page), "numOfRows", Integer.toString(POSITION_PAGE), "resultType", "json"));
            JsonNode doc = parse(body);
            JsonNode head = doc.path("response").path("header");
            if (!"00".equals(text(head.get("resultCode")))) {
                throw new PublicDataException("공공데이터포털 오류 " + text(head.get("resultCode")) + ": " + text(head.get("resultMsg")));
            }
            JsonNode b = doc.path("response").path("body");
            Double total = num(b.get("totalCount"));
            if (total != null && total > (double) POSITION_PAGE * POSITION_MAX_PAGES) {
                throw new PublicDataException("선박 위치가 5,000척을 넘음");
            }
            List<JsonNode> got = items(b.path("items").path("item"));
            out.addAll(got);
            if (total == null || out.size() >= total || got.isEmpty() || page >= POSITION_MAX_PAGES) {
                return out;
            }
        }
    }

    public Map<String, Object> voyage(String callsgn, String year, String voyage) {
        String key = callsgn + "|" + year;
        CachedVoyage hit;
        synchronized (voyages) { // 잠금은 캐시를 읽고 쓰는 순간만 — API를 부르는 동안 다른 배의 조회를 막지 않는다
            hit = voyages.get(key);
        }
        boolean stale = false;
        String error = null;
        if (hit == null || clock.instant().isAfter(hit.at().plus(props.voyageCache()))) {
            try {
                CachedVoyage fresh = new CachedVoyage(clock.instant(), fetchVoyages(callsgn, year));
                synchronized (voyages) {
                    voyages.put(key, fresh);
                }
                hit = fresh;
            } catch (PublicDataException e) {
                if (hit == null) {
                    throw e;
                }
                stale = true; // 실패하면 예전에 받아 둔 기록을 stale로 내려 준다
                error = e.getMessage();
            }
        }
        TreeSet<String> all = new TreeSet<>();
        List<Map<String, Object>> ev = new ArrayList<>();
        for (Map<String, Object> e : hit.events()) {
            if (e.get("voyage") != null) {
                all.add((String) e.get("voyage"));
            }
            if (voyage == null || voyage.equals(e.get("voyage"))) {
                ev.add(e);
            }
        }
        ev.sort(Comparator.comparing(e -> e.get("eventAt") == null ? "" : (String) e.get("eventAt")));
        Map<String, Object> doc = new LinkedHashMap<>();
        doc.put("source", "울산항만공사 항만 내 선박 운항정보 (공공데이터포털 15156628)");
        doc.put("callSign", callsgn);
        doc.put("year", year);
        doc.put("voyage", voyage);
        doc.put("voyages", new ArrayList<>(all));
        doc.put("events", ev);
        if (stale) {
            doc.put("stale", true);
            doc.put("error", error);
        }
        return doc;
    }

    private List<Map<String, Object>> fetchVoyages(String callsgn, String year) {
        byte[] body = client.get(VOYAGE, Map.of(
                "pageNo", "1", "numOfRows", "200", "resultType", "json", "callsgn", callsgn, "ptentVtsYr", year));
        JsonNode doc = parse(body);
        if (!doc.has("response")) { // 키·변수 오류는 OpenAPI_ServiceResponse로 온다
            throw new PublicDataException("공공데이터포털 오류 "
                    + text(doc.path("OpenAPI_ServiceResponse").path("cmmMsgHeader").get("returnReasonCode")));
        }
        List<Map<String, Object>> out = new ArrayList<>();
        for (JsonNode r : items(doc.path("response").path("body").path("items").path("item"))) {
            Map<String, Object> e = new LinkedHashMap<>();
            e.put("voyage", text(r.get("vyg")));
            e.put("event", text(r.get("ioprtVtsNm")));
            e.put("facility", text(r.get("fcltKornNm")));
            e.put("facilityCode", text(r.get("fcltSpecCd")));
            e.put("arrivedAt", iso(compact(text(r.get("ptentDt")))));
            e.put("departedAt", iso(compact(text(r.get("dfptDt")))));
            e.put("eventAt", iso(compact(text(r.get("jobDt")))));
            e.put("updatedAt", iso(compact(text(r.get("updtDt")))));
            out.add(e);
        }
        return out;
    }

    private JsonNode parse(byte[] body) {
        try {
            return json.readTree(body);
        } catch (RuntimeException e) {
            throw new PublicDataException("공공데이터포털 응답이 JSON이 아님 (키 미승인·트래픽 초과일 수 있음)");
        }
    }

    static List<JsonNode> items(JsonNode item) {
        List<JsonNode> out = new ArrayList<>();
        if (item == null || item.isMissingNode() || item.isNull()) {
            return out;
        }
        if (item.isArray()) {
            out.addAll(item.values());
        } else if (item.isObject()) {
            out.add(item);
        }
        return out;
    }

    /** 빈 값과 문자열 "None"은 값 없음(demo/docs/16 #16 데이터 품질). */
    static String text(JsonNode n) {
        if (n == null || n.isNull() || n.isMissingNode()) {
            return null;
        }
        String s = n.asString();
        return s.isBlank() || "None".equals(s) ? null : s;
    }

    static Double num(JsonNode n) {
        String s = text(n);
        if (s == null) {
            return null;
        }
        try {
            return Double.parseDouble(s.strip());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    static Integer integer(JsonNode n) {
        String s = text(n);
        if (s == null) {
            return null;
        }
        try {
            return Integer.parseInt(s.strip());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    static OffsetDateTime compact(String s) {
        if (s == null) {
            return null;
        }
        try {
            return LocalDateTime.parse(s, COMPACT).atZone(KST).toOffsetDateTime();
        } catch (DateTimeParseException e) {
            return null;
        }
    }

    static String iso(OffsetDateTime t) {
        return t == null ? null : t.format(OUT);
    }
}
