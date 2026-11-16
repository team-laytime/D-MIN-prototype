package com.dmin.publicdata;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.dmin.common.error.DminException;
import com.dmin.common.error.ErrorCode;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

/** 공공데이터포털을 실제로 부르지 않고(가짜 클라이언트) 쪽 넘김·캐시·실패 처리·입력 범위를 본다. */
class PublicDataFetchTest {

    private static final PublicDataProperties PROPS = new PublicDataProperties("test-key", "https://apis.example.invalid",
            Duration.ofSeconds(30), Duration.ofMinutes(5), Duration.ofMinutes(5), Duration.ofSeconds(5));

    private final JsonMapper json = JsonMapper.builder().build();
    private final TestClock clock = new TestClock(Instant.parse("2026-11-12T08:10:00Z")); // 17:10 KST

    /** 부른 쪽 번호를 적어 두고 준비한 본문을 돌려준다. */
    private static final class FakeClient extends PublicDataClient {
        final List<Map<String, String>> calls = new ArrayList<>();
        private final Function<Map<String, String>, byte[]> answer;

        FakeClient(Function<Map<String, String>, byte[]> answer) {
            super(PROPS);
            this.answer = answer;
        }

        @Override
        byte[] get(String path, Map<String, String> params) {
            calls.add(params);
            return answer.apply(params);
        }
    }

    private static final class TestClock extends Clock {
        Instant now;

        TestClock(Instant now) {
            this.now = now;
        }

        @Override
        public ZoneId getZone() {
            return ZoneId.of("Asia/Seoul");
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return now;
        }
    }

    /** 선박 위치 한 쪽: from번부터 count척 (모두 17:00 KST 갱신). */
    private static byte[] positions(int total, int from, int count) {
        StringBuilder items = new StringBuilder();
        for (int i = from; i < from + count; i++) {
            items.append(i > from ? "," : "")
                    .append("{\"mmsiNo\":\"").append(i).append("\",\"lat\":\"35.4\",\"lot\":\"129.3\",\"updtTm\":\"20261112170000\"}");
        }
        return ("{\"response\":{\"header\":{\"resultCode\":\"00\",\"resultMsg\":\"NORMAL SERVICE.\"},\"body\":{\"totalCount\":" + total
                + ",\"items\":{\"item\":[" + items + "]}}}}").getBytes(StandardCharsets.UTF_8);
    }

    private static byte[] voyages(String vyg) {
        return ("{\"response\":{\"header\":{\"resultCode\":\"00\"},\"body\":{\"items\":{\"item\":[{\"vyg\":\"" + vyg
                + "\",\"ioprtVtsNm\":\"입항\",\"jobDt\":\"20261112170000\"}]}}}}").getBytes(StandardCharsets.UTF_8);
    }

    private static byte[] entries(long total) {
        return ("<response><header><resultCode>00</resultCode></header><body><items></items><totalCount>" + total
                + "</totalCount></body></response>").getBytes(StandardCharsets.UTF_8);
    }

    @Test
    void positionsArePagedUntilTotalCount() {
        int total = 2500;
        FakeClient c = new FakeClient(p -> {
            int size = Integer.parseInt(p.get("numOfRows"));
            int from = (Integer.parseInt(p.get("pageNo")) - 1) * size;
            return positions(total, from, Math.max(0, Math.min(size, total - from)));
        });
        Map<String, Object> doc = new AisService(c, PROPS, json, clock).vessels(60, null);
        assertEquals(2500, doc.get("total"));
        assertEquals(List.of("1", "2", "3"), c.calls.stream().map(p -> p.get("pageNo")).toList());
        assertTrue(c.calls.stream().allMatch(p -> "1000".equals(p.get("numOfRows"))));
    }

    @Test
    void moreThan5000PositionsIsAnErrorNotAPartialMap() {
        FakeClient c = new FakeClient(p -> positions(5001, 0, 1000));
        AisService ais = new AisService(c, PROPS, json, clock);
        PublicDataException e = assertThrows(PublicDataException.class, () -> ais.vessels(60, null));
        assertEquals("선박 위치가 5,000척을 넘음", e.getMessage());
        assertEquals(1, c.calls.size());
    }

    @Test
    void voyageFailureServesTheLastGoodCopyAsStale() {
        boolean[] down = {false};
        FakeClient c = new FakeClient(p -> {
            if (down[0]) {
                throw new PublicDataException("공공데이터포털 응답 500");
            }
            return voyages("022");
        });
        AisService ais = new AisService(c, PROPS, json, clock);
        assertNull(ais.voyage("D7IN", "2026", null).get("stale"));
        down[0] = true;
        clock.now = clock.now.plus(Duration.ofMinutes(6)); // 5분 캐시가 지났다
        Map<String, Object> old = ais.voyage("D7IN", "2026", null);
        assertEquals(true, old.get("stale"));
        assertEquals("공공데이터포털 응답 500", old.get("error"));
        assertEquals(List.of("022"), old.get("voyages"));
        assertThrows(PublicDataException.class, () -> ais.voyage("OTHER", "2026", null)); // 받아 둔 것이 없으면 그대로 실패
    }

    @Test
    void voyageCacheKeepsTheLatest256Vessels() {
        FakeClient c = new FakeClient(p -> voyages("001"));
        AisService ais = new AisService(c, PROPS, json, clock);
        for (int i = 0; i <= 256; i++) { // 257척
            ais.voyage("V" + i, "2026", null);
        }
        assertEquals(257, c.calls.size());
        ais.voyage("V256", "2026", null); // 최근에 본 것은 캐시에서
        assertEquals(257, c.calls.size());
        ais.voyage("V0", "2026", null); // 가장 오래 안 본 것은 밀려나 다시 받는다
        assertEquals(258, c.calls.size());
    }

    @Test
    void tooManyEntryRowsStopOnTheFirstPage() {
        FakeClient c = new FakeClient(p -> entries(2001)); // 50건 × 40쪽 = 2,000건을 넘음
        PublicDataException e = assertThrows(PublicDataException.class, () -> new EntryService(c, PROPS, clock).snapshot(true));
        assertTrue(e.getMessage().contains("2001건"), e.getMessage());
        assertEquals(1, c.calls.size());
    }

    @Test
    void badBaseUrlNeverPutsTheKeyInTheMessage() {
        PublicDataProperties bad = new PublicDataProperties("SECRET+KEY/123==", "https://bad host", Duration.ofSeconds(30),
                Duration.ofMinutes(5), Duration.ofMinutes(5), Duration.ofSeconds(5));
        PublicDataException e = assertThrows(PublicDataException.class, () -> new PublicDataClient(bad).get("/x", Map.of("pageNo", "1")));
        assertEquals("공공데이터포털 주소 형식 오류 (dmin.public-data.base-url 확인)", e.getMessage());
    }

    @Test
    void controllerRejectsOutOfRangeWindows() {
        FakeClient c = new FakeClient(p -> {
            throw new AssertionError("입력 검사에서 막혀야 한다");
        });
        PublicDataController ctl = new PublicDataController(new AisService(c, PROPS, json, clock), new EntryService(c, PROPS, clock), PROPS);
        for (double[] bad : new double[][] {{-1, 48}, {0, 241}, {Double.NaN, 48}, {0, Double.POSITIVE_INFINITY}}) {
            DminException e = assertThrows(DminException.class, () -> ctl.arrivals(null, bad[0], bad[1]));
            assertEquals(ErrorCode.VALIDATION, e.errorCode());
        }
        for (double age : new double[] {0, -5, 1441, Double.NaN}) {
            DminException e = assertThrows(DminException.class, () -> ctl.vessels(age, null));
            assertEquals(ErrorCode.VALIDATION, e.errorCode());
        }
        assertTrue(c.calls.isEmpty());
    }
}
