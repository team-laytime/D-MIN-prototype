package com.dmin.laytime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * 규칙 해석 묶음(profiles)과 팀원 코드 해석으로 새로 생긴 규칙 3개.
 *   야간 도선 대상 '3만 이상 수입선' · Last POB를 ETA 날짜와만 비교(ETA_DAY) · 새벽 금지는 대상 선박에만(SUBJECT) · Buoy 최소 DWT
 * Python pptcalc와 같은 해석인지는 GoldenCrossCheckTest의 팀 해석 정답 파일이 지킨다.
 */
class TeamProfileTest {

    static final Map<String, Object> TEAM = Rules.profilePatch("team", Map.of());

    @Test
    void profilesComeFromTheRulesTable() {
        assertTrue(Rules.profileNames().containsAll(List.of("ppt", "team")));
        assertFalse(Rules.profileNames().contains("_doc"));
        Map<String, Object> p = Rules.profilePatch("team", Map.of("demurrage.weather_basis", "WAIT", "work.setup_h", 1.0));
        assertEquals("DEMURRAGE", p.get("demurrage.weather_basis"), "실행할 때 고른 해석이 데이터의 rule_patch보다 앞선다");
        assertEquals(1.0, p.get("work.setup_h"), "해석에 없는 데이터 patch는 그대로 남는다");
        assertEquals(Map.of(), Rules.profilePatch("ppt", Map.of()));
        assertThrows(IllegalArgumentException.class, () -> Rules.profilePatch("nope", Map.of()));
        assertThrows(IllegalArgumentException.class, () -> Rules.profilePatch("_doc", Map.of()));
        Rules team = Rules.bundled(TEAM);
        assertEquals("DEMURRAGE", team.weatherBasis());
        assertTrue(team.dawnSubjectOnly);
        assertEquals("ETA_DAY", team.pobCompare);
        assertEquals(80000.0, team.minDwt.get("BUOY2"));
        assertThrows(IllegalArgumentException.class, () -> Rules.bundled(Map.of("night_pilotage.dawn.scope", "ALL")));
    }

    @Test
    void dawnBanAppliesToEveryLargeShipUnderPptButOnlyToSubjectsUnderTeam() throws IOException {
        // C: GRT 42,141 수출선 → PPT 글자 그대로면 새벽 금지(GRT 3만 이상), 팀원 코드면 야간 도선 대상이 아니라 금지 없음
        long etb = Times.parse("2026-11-10T03:00");
        assertEquals(Times.parse("2026-11-10T08:00"), etbAfterWindows(Rules.bundled(), "C", "2026-11-10T01:30", 42141, "EX", "#8", etb));
        assertEquals(etb, etbAfterWindows(Rules.bundled(TEAM), "C", "2026-11-10T01:30", 42141, "EX", "#8", etb));
        // GRT 8만(항상 대상)은 두 해석 모두 새벽 금지
        assertEquals(Times.parse("2026-11-10T08:00"), etbAfterWindows(Rules.bundled(TEAM), "C", "2026-11-10T01:30", 80000, "EX", "#8", etb));
    }

    @Test
    void afterMidnightArrivalIsLastPobOnlyUnderPpt() throws IOException {
        // GRT 8만 선박이 00:10 도착, ETB 01:00(새벽 02~08시 밖): PPT('ETA')는 전날 Last POB 뒤 도착이라 08시까지 금지, 팀(ETA_DAY)은 그날 Last POB 전이라 통과
        long etb = Times.parse("2026-11-10T01:00");
        assertEquals(Times.parse("2026-11-10T08:00"), etbAfterWindows(Rules.bundled(), "C", "2026-11-10T00:10", 80000, "EX", "#8", etb));
        assertEquals(etb, etbAfterWindows(Rules.bundled(TEAM), "C", "2026-11-10T00:10", 80000, "EX", "#8", etb));
    }

    @Test
    void buoyMinimumDwtOnlyUnderTeam() throws IOException {
        Rules ppt = Rules.bundled();
        Rules team = Rules.bundled(TEAM);
        CaseData.Arrival small = arrival(ppt, "A", "2026-11-10T06:00", 29597, "IM", "CRUDE", "CR", 45000);
        assertFalse(Calc.ineligible(ppt, small, "BUOY2").stream().anyMatch(s -> s.contains("최소")));
        assertTrue(Calc.ineligible(team, arrival(team, "A", "2026-11-10T06:00", 29597, "IM", "CRUDE", "CR", 45000), "BUOY2")
                .contains("DWT 45,000 < 최소 80,000"));
    }

    // ------------------------------------------------------------------ 예시 3척 요청을 조금 바꿔 쓴다
    private static long etbAfterWindows(Rules rules, String id, String eta, double grt, String biz, String bid, long tau) throws IOException {
        JsonNode doc = doc(id, eta, grt, biz, null, null, null);
        CaseData cs = CaseParser.parse(doc, rules).data();
        return Calc.phi(Calc.windowsOf(rules, cs, cs.arrivals().get(id), bid), tau).from();
    }

    private static CaseData.Arrival arrival(Rules rules, String id, String eta, double grt, String biz, String cargo, String cls, double dwt)
            throws IOException {
        CaseParser.Parsed p = CaseParser.parse(doc(id, eta, grt, biz, cargo, cls, dwt), rules);
        assertTrue(p.ok(), () -> "입력 검사 실패: " + p.errors());
        return p.data().arrivals().get(id);
    }

    private static JsonNode doc(String id, String eta, double grt, String biz, String cargo, String cls, Double dwt) throws IOException {
        ObjectNode doc = (ObjectNode) Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/EXAMPLE-3.request.json"));
        doc.remove("current_plan");
        for (JsonNode n : doc.get("arrivals").values()) {
            ObjectNode a = (ObjectNode) n;
            if (a.get("id").asString().equals(id)) {
                a.put("eta", eta);
                a.put("grt", grt);
                a.put("biz", biz);
                if (cargo != null) {
                    a.put("cargo_group", cargo);
                    a.put("class", cls);
                    a.put("dwt", dwt);
                }
            }
        }
        return doc;
    }
}
