package com.dmin.publicdata;

import java.io.ByteArrayInputStream;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.springframework.stereotype.Service;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

/**
 * 해양수산부 선박입출항신고(15006353, 1192000/VsslEtrynd5/Info5) — 울산(항만청 820). demo/src/demurrage/data/entry.py를 옮긴 것이다.
 * 대리점이 낸 입항 신고라 '입항 예정 일시 = ETA'가 들어 있다. 같은 입항에 최초·변경·최종 신고가 쌓이므로 가장 나중 단계 하나만 쓴다.
 * 응답은 XML이다. 외부 개체(XXE)를 막은 파서로 읽는다.
 */
@Service
public class EntryService {

    static final String PATH = "/1192000/VsslEtrynd5/Info5";
    static final String ULSAN = "820";
    private static final Map<String, Integer> RANK = Map.of("최초", 1, "변경", 2, "최종", 3);
    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("yyyyMMdd");
    private static final int PAGE = 50;
    private static final int MAX_PAGES = 40;

    private final PublicDataClient client;
    private final PublicDataProperties props;
    private final Clock clock;

    private List<Map<String, Object>> rows;
    private Instant rowsAt = Instant.EPOCH;
    private String fetchedAt;
    private List<String> window;

    EntryService(PublicDataClient client, PublicDataProperties props, Clock clock) {
        this.client = client;
        this.props = props;
        this.clock = clock;
    }

    public record Snapshot(List<Map<String, Object>> rows, String fetchedAt, List<String> window, boolean stale, String error) {}

    /** 조회 창(−3일 ~ +10일)의 신고 전체. 5분 캐시, 실패하면 마지막 성공값(stale). force면 캐시를 무시한다(수집 CronJob). */
    public Snapshot snapshot(boolean force) {
        synchronized (this) {
            boolean expired = rows == null || clock.instant().isAfter(rowsAt.plus(props.entryCache()));
            if (force || expired) {
                OffsetDateTime now = OffsetDateTime.now(clock);
                String sde = now.minusDays(3).format(DAY);
                String ede = now.plusDays(10).format(DAY);
                try {
                    rows = fetch(sde, ede);
                    rowsAt = clock.instant();
                    fetchedAt = now.format(AisService.OUT);
                    window = List.of(sde, ede);
                } catch (PublicDataException e) {
                    if (rows == null || force) {
                        throw e;
                    }
                    return new Snapshot(rows, fetchedAt, window, true, e.getMessage());
                }
            }
            return new Snapshot(rows, fetchedAt, window, false, null);
        }
    }

    public Map<String, Object> arrivals(String callsgn, double hoursBack, double hoursAhead) {
        Snapshot snap = snapshot(false);
        OffsetDateTime now = OffsetDateTime.now(clock);
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> r : pickLatest(snap.rows())) {
            OffsetDateTime eta = time((String) r.get("eta"));
            if (eta == null) {
                continue;
            }
            boolean keep;
            if (callsgn != null) {
                keep = callsgn.equals(r.get("callSign"));
            } else {
                OffsetDateTime lo = now.minusMinutes(Math.round(hoursBack * 60));
                OffsetDateTime hi = now.plusMinutes(Math.round(hoursAhead * 60));
                keep = !eta.isBefore(lo) && !eta.isAfter(hi);
            }
            if (keep) {
                Map<String, Object> copy = new LinkedHashMap<>(r);
                copy.put("planned", eta.isAfter(now));
                out.add(copy);
            }
        }
        out.sort(Comparator.comparing(r -> time((String) r.get("eta"))));
        Map<String, Object> doc = new LinkedHashMap<>();
        doc.put("source", "해양수산부 선박입출항신고 (공공데이터포털 15006353) · 울산 820");
        doc.put("fetchedAt", snap.fetchedAt());
        doc.put("window", snap.window());
        doc.put("stale", snap.stale());
        doc.put("count", out.size());
        doc.put("arrivals", out);
        if (snap.error() != null) {
            doc.put("error", snap.error());
        }
        return doc;
    }

    /** 같은 입항(호출부호·연도·입항횟수)의 입항 신고 중 가장 나중 단계(최종 > 변경 > 최초) 하나. */
    public static List<Map<String, Object>> pickLatest(List<Map<String, Object>> rows) {
        Map<String, Map<String, Object>> best = new LinkedHashMap<>();
        for (Map<String, Object> r : rows) {
            if (!"입항".equals(r.get("event")) || r.get("eta") == null) {
                continue;
            }
            String k = r.get("callSign") + "|" + r.get("year") + "|" + r.get("count");
            Map<String, Object> cur = best.get(k);
            if (cur == null || rank(r.get("filing")) >= rank(cur.get("filing"))) {
                best.put(k, r);
            }
        }
        return new ArrayList<>(best.values());
    }

    /** 신고 단계 순위. 단계가 비었거나(null) 모르는 값이면 0 — Map.of는 null 키를 물으면 NPE를 던진다. */
    private static int rank(Object filing) {
        Integer r = filing == null ? null : RANK.get(filing);
        return r == null ? 0 : r;
    }

    private List<Map<String, Object>> fetch(String sde, String ede) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (int page = 1; ; page++) {
            byte[] body = client.get(PATH, Map.of(
                    "pageNo", Integer.toString(page), "numOfRows", Integer.toString(PAGE), "prtAgCd", ULSAN, "sde", sde, "ede", ede));
            Parsed p = parse(body);
            if (page == 1 && p.total() > (long) PAGE * MAX_PAGES) { // 첫 쪽에서 총 건수를 보고 바로 멈춘다(40쪽을 다 받은 뒤가 아니라)
                throw new PublicDataException("조회 건수 " + p.total() + "건이 너무 많아 일부만 받을 수 있습니다. 조회 기간을 줄이세요");
            }
            for (Map<String, String> raw : p.rows()) {
                out.add(normalize(raw));
            }
            if ((long) page * PAGE >= p.total()) {
                return out;
            }
            if (page >= MAX_PAGES) { // 2,000건을 넘으면 창이 너무 넓다. 일부만 받은 채 통과시키지 않는다.
                throw new PublicDataException("조회 건수 " + p.total() + "건이 너무 많아 일부만 받을 수 있습니다. 조회 기간을 줄이세요");
            }
        }
    }

    record Parsed(long total, List<Map<String, String>> rows) {}

    /** 응답 XML → (총 건수, 행). 신고 한 건(item)에 상세(detail)가 여러 줄 있어 한 줄씩 펼친다. */
    static Parsed parse(byte[] xml) {
        Document doc;
        try {
            DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
            f.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            f.setExpandEntityReferences(false);
            DocumentBuilder b = f.newDocumentBuilder();
            doc = b.parse(new ByteArrayInputStream(xml));
        } catch (Exception e) {
            throw new PublicDataException("공공데이터포털 응답이 XML이 아님");
        }
        Element root = doc.getDocumentElement();
        if ("OpenAPI_ServiceResponse".equals(root.getTagName())) { // 키·서비스 오류는 이 모양
            throw new PublicDataException("공공데이터포털 오류 " + first(root, "returnReasonCode"));
        }
        String code = first(root, "resultCode");
        if (code != null && !"00".equals(code)) {
            throw new PublicDataException("공공데이터포털 오류 " + code + ": " + first(root, "resultMsg"));
        }
        List<Map<String, String>> rows = new ArrayList<>();
        NodeList items = root.getElementsByTagName("item");
        for (int i = 0; i < items.getLength(); i++) {
            Element it = (Element) items.item(i);
            Map<String, String> base = new LinkedHashMap<>();
            for (Node c = it.getFirstChild(); c != null; c = c.getNextSibling()) {
                if (c instanceof Element e && !"details".equals(e.getTagName())) {
                    base.put(e.getTagName(), e.getTextContent());
                }
            }
            NodeList details = it.getElementsByTagName("detail");
            for (int j = 0; j < details.getLength(); j++) {
                Map<String, String> row = new LinkedHashMap<>(base);
                for (Node c = details.item(j).getFirstChild(); c != null; c = c.getNextSibling()) {
                    if (c instanceof Element e) {
                        row.put(e.getTagName(), e.getTextContent());
                    }
                }
                rows.add(row);
            }
        }
        String total = first(root, "totalCount");
        long count = 0;
        if (total != null && !total.isBlank()) {
            try {
                count = Long.parseLong(total.strip());
            } catch (NumberFormatException e) {
                throw new PublicDataException("공공데이터포털 응답의 totalCount가 숫자가 아님");
            }
        }
        return new Parsed(count, rows);
    }

    private static String first(Element root, String tag) {
        NodeList n = root.getElementsByTagName(tag);
        return n.getLength() == 0 ? null : n.item(0).getTextContent();
    }

    static Map<String, Object> normalize(Map<String, String> r) {
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("callSign", txt(r.get("clsgn")));
        v.put("year", txt(r.get("etryptYear")));
        v.put("count", txt(r.get("etryptCo")));
        v.put("name", txt(r.get("vsslNm")));
        v.put("flag", txt(r.get("vsslNltyNm")));
        v.put("type", txt(r.get("vsslKndNm")));
        v.put("purpose", txt(r.get("etryptPurpsNm")));
        v.put("event", txt(r.get("etryndNm")));
        v.put("filing", txt(r.get("reqstSeNm")));
        v.put("eta", txt(r.get("etryptDt"))); // 입항일시(신고). 미래면 입항 예정
        String etd = txt(r.get("tkoffDt"));
        v.put("etd", etd != null ? etd : txt(r.get("tkoffPrrrnDt")));
        v.put("prevPort", txt(r.get("prvsDpmprtPrtNm")));
        v.put("firstPort", txt(r.get("frstDpmprtPrtNm")));
        v.put("nextPort", txt(r.get("nxlnptPrtNm")));
        v.put("destPort", txt(r.get("dstnPrtNm")));
        v.put("facility", txt(r.get("laidupFcltyNm")));
        v.put("facilityCode", txt(r.get("laidupFcltyCd")));
        v.put("domestic", txt(r.get("ibobprtNm")));
        v.put("pilot", txt(r.get("piltgYn")));
        v.put("tug", txt(r.get("tugYn")));
        v.put("grt", num(r.get("grtg")));
        v.put("intlGrt", num(r.get("intrlGrtg")));
        v.put("crew", num(r.get("crewCo")));
        v.put("cargo", txt(r.get("ldadngFrghtClCd")));
        v.put("loadTon", num(r.get("ldFrghtTon")));
        v.put("unloadTon", num(r.get("landngFrghtTon")));
        v.put("agent", txt(r.get("satmntEntrpsNm")));
        return v;
    }

    static String txt(String v) {
        return v == null || v.isBlank() || "None".equals(v) ? null : v.strip();
    }

    static Double num(String v) {
        String s = txt(v);
        if (s == null) {
            return null;
        }
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** 신고 시각: "2026-11-12T20:00:00+09:00" · "2026-11-12 20:00:00"(KST) · "20261112200000" 모두 받는다. */
    static OffsetDateTime time(String s) {
        if (s == null) {
            return null;
        }
        try {
            return OffsetDateTime.parse(s);
        } catch (DateTimeParseException ignored) {
            // 아래 형식들을 차례로
        }
        try {
            return LocalDateTime.parse(s.replace(' ', 'T')).atZone(AisService.KST).toOffsetDateTime();
        } catch (DateTimeParseException ignored) {
            // 다음
        }
        return AisService.compact(s);
    }
}
