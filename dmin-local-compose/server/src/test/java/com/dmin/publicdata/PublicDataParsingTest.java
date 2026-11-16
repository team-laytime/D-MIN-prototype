package com.dmin.publicdata;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/** 실제 API는 부르지 않고 응답 모양으로만 확인한다 (demo/tests/test_ais.py·test_entry.py와 같은 사례). */
class PublicDataParsingTest {

    private final JsonMapper json = JsonMapper.builder().build();

    @Test
    void positionRowMapsLikeThePythonAdapter() {
        JsonNode raw = json.readTree("""
                {"callsgn":"D7IN","ptentYr":"2026","vyg":"022","mmsiNo":"440321000","imoNo":"9879363","vslNm":"싸왓디 퍼시픽",
                 "lot":"129.35579667","lat":"35.44168167","sog":"0","cog":"279","rot":"0","hdgAng":"245","drft":"9.5",
                 "nvgtStts":"정박(계류)","updtTm":"20261112170635"}""");
        OffsetDateTime now = OffsetDateTime.parse("2026-11-12T17:16:35+09:00");
        Map<String, Object> v = AisService.normalize(raw, now);
        assertEquals("440321000", v.get("mmsi"));
        assertEquals(35.44168167, v.get("lat"));
        assertEquals(279, v.get("cog"));
        assertEquals(9.5, v.get("draft"));
        assertEquals(10.0, v.get("ageMin"));
        assertEquals("2026-11-12T17:06:35+09:00", v.get("updatedAt"));
    }

    @Test
    void blanksAndNoneBecomeNull() {
        assertNull(AisService.normalize(json.readTree("{\"lat\":\"\",\"lot\":\"129.3\"}"), OffsetDateTime.now()));
        Map<String, Object> v = AisService.normalize(
                json.readTree("{\"lat\":\"35.4\",\"lot\":\"129.3\",\"imoNo\":\"\",\"drft\":\"0\",\"vslNm\":\"None\"}"),
                OffsetDateTime.now());
        assertNull(v.get("imo"));
        assertNull(v.get("draft"));
        assertEquals("", v.get("name"));
    }

    private static String item(String clsgn, String count, String... details) {
        StringBuilder ds = new StringBuilder();
        for (String d : details) {
            String[] p = d.split("\\|");
            ds.append("<detail><reqstSeNm>").append(p[0]).append("</reqstSeNm><etryndNm>").append(p[1])
                    .append("</etryndNm><etryptDt>").append(p[2]).append("</etryptDt><laidupFcltyNm>").append(p[3])
                    .append("</laidupFcltyNm><grtg>23386</grtg><tkoffDt/></detail>");
        }
        return "<item><prtAgCd>820</prtAgCd><etryptYear>2026</etryptYear><etryptCo>" + count + "</etryptCo><clsgn>" + clsgn
                + "</clsgn><vsslNm>ISLAND BAY</vsslNm><prvsDpmprtPrtNm>CALLAO</prvsDpmprtPrtNm><dstnPrtNm></dstnPrtNm><details>" + ds
                + "</details></item>";
    }

    private static byte[] xml(int total, String... items) {
        return ("<response><header><resultCode>00</resultCode><resultMsg>NORMAL_SERVICE</resultMsg></header><body><items>"
                        + String.join("", items) + "</items><totalCount>" + total + "</totalCount></body></response>")
                .getBytes(StandardCharsets.UTF_8);
    }

    @Test
    void entryXmlFlattensDetailsAndPicksTheLatestFiling() {
        EntryService.Parsed p = EntryService.parse(xml(2,
                item("VRNJ4", "092", "최초|입항|2026-11-12T20:00:00+09:00|정박지-E2", "변경|입항|2026-11-12T22:00:00+09:00|정박지-E2",
                        "최초|출항|2026-11-14T08:00:00+09:00|E2"),
                item("VRNJ4", "093", "최초|입항|2026-11-20T08:00:00+09:00|E3")));
        assertEquals(2, p.total());
        assertEquals(4, p.rows().size());
        List<Map<String, Object>> rows = p.rows().stream().map(EntryService::normalize).toList();
        Map<String, Object> first = rows.getFirst();
        assertEquals("VRNJ4", first.get("callSign"));
        assertEquals(23386.0, first.get("grt"));
        assertNull(first.get("destPort"));
        List<Map<String, Object>> latest = EntryService.pickLatest(rows);
        assertEquals(2, latest.size());
        Map<String, Object> v092 = latest.stream().filter(r -> "092".equals(r.get("count"))).findFirst().orElseThrow();
        assertEquals("변경", v092.get("filing"));
        assertTrue(((String) v092.get("eta")).startsWith("2026-11-12T22"));
    }

    @Test
    void emptyFilingStageDoesNotThrow() {
        Map<String, Object> blank = new HashMap<>(Map.of("event", "입항", "eta", "2026-11-12T20:00:00+09:00", "callSign", "VRNJ4",
                "year", "2026", "count", "092"));
        blank.put("filing", null); // 신고 단계 칸이 빈 줄 (Map.of 순위 표에 null을 물으면 NPE였다)
        Map<String, Object> first = new HashMap<>(blank);
        first.put("filing", "최초");
        List<Map<String, Object>> latest = assertDoesNotThrow(() -> EntryService.pickLatest(List.of(blank, first, new HashMap<>(blank))));
        assertEquals(1, latest.size());
        assertEquals("최초", latest.getFirst().get("filing")); // 단계를 모르는 줄은 아는 단계를 덮지 않는다
    }

    @Test
    void nonNumericTotalCountIsAnError() {
        byte[] body = ("<response><header><resultCode>00</resultCode></header><body><items></items><totalCount>abc</totalCount></body>"
                + "</response>").getBytes(StandardCharsets.UTF_8);
        PublicDataException e = assertThrows(PublicDataException.class, () -> EntryService.parse(body));
        assertEquals("공공데이터포털 응답의 totalCount가 숫자가 아님", e.getMessage());
    }

    @Test
    void serviceErrorIsAnErrorNotAnEmptyList() {
        byte[] err = "<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
                .getBytes(StandardCharsets.UTF_8);
        PublicDataException e = assertThrows(PublicDataException.class, () -> EntryService.parse(err));
        assertTrue(e.getMessage().contains("30"));
    }

    @Test
    void xmlWithDoctypeIsRejected() {
        byte[] xxe = "<?xml version=\"1.0\"?><!DOCTYPE r [<!ENTITY x SYSTEM \"file:///etc/passwd\">]><response>&x;</response>"
                .getBytes(StandardCharsets.UTF_8);
        assertThrows(PublicDataException.class, () -> EntryService.parse(xxe));
    }

    @Test
    void entryTimesInThreeShapes() {
        assertEquals(OffsetDateTime.parse("2026-11-12T20:00:00+09:00"), EntryService.time("2026-11-12T20:00:00+09:00"));
        assertEquals(OffsetDateTime.parse("2026-11-12T20:00:00+09:00"), EntryService.time("2026-11-12 20:00:00"));
        assertEquals(OffsetDateTime.parse("2026-11-12T20:00:00+09:00"), EntryService.time("20261112200000"));
    }
}
