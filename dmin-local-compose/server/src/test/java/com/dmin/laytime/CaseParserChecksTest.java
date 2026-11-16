package com.dmin.laytime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.util.List;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * 입구 검사(FR-01~04): Python이 다르게 읽을 값은 실행 전에 막는다.
 * 예) berths: "*" 는 어느 부두에도 안 걸리고, cfr: "false" 는 Python에서 참이 된다.
 */
class CaseParserChecksTest {

    private final Rules rules = Rules.bundled();

    private static ObjectNode example() throws IOException {
        return (ObjectNode) Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/EXAMPLE-3.request.json"));
    }

    private static ObjectNode arrival(ObjectNode doc, int i) {
        return (ObjectNode) doc.get("arrivals").get(i);
    }

    private List<String> errors(JsonNode doc) {
        return CaseParser.parse(doc, rules).errors();
    }

    @Test
    void exampleIsClean() throws IOException {
        CaseParser.Parsed p = CaseParser.parse(example(), rules);
        assertTrue(p.ok(), p.errors()::toString);
        assertTrue(p.data().currentPlan().isEmpty());
    }

    @Test
    void restrictionBerthsMustBeAnArrayOfStrings() throws IOException {
        for (String bad : List.of("\"*\"", "[]", "[1]", "null")) {
            ObjectNode doc = example();
            ((ObjectNode) doc.get("restrictions").get(0)).set("berths", Rules.JSON.readTree(bad));
            List<String> errs = errors(doc);
            assertTrue(errs.contains("restrictions[1].berths는 문자열 배열이어야 함 (전 부두는 [\"*\"])"), () -> bad + " → " + errs);
        }
    }

    @Test
    void cfrAndWeatherHalfMustBeTrueOrFalse() throws IOException {
        ObjectNode doc = example();
        ((ObjectNode) arrival(doc, 0).get("contract")).put("cfr", "true");
        ((ObjectNode) arrival(doc, 1).get("contract")).putNull("weather_half");
        List<String> errs = errors(doc);
        assertTrue(errs.contains("arrivals[1] (A).contract.cfr는 true/false"), errs::toString);
        assertTrue(errs.contains("arrivals[2] (B).contract.weather_half는 true/false"), errs::toString);
        assertEquals(2, errs.size(), errs::toString);
    }

    @Test
    void negativeQuantitiesAreErrors() throws IOException {
        ObjectNode doc = example();
        arrival(doc, 0).put("qty", -1);
        ((ObjectNode) arrival(doc, 1).get("work")).put("hours", -5);
        ((ObjectNode) arrival(doc, 2).get("work")).put("rate_per_h", 0);
        ((ObjectNode) arrival(doc, 3).get("work")).putObject("by_berth").put("#8", -100);
        List<String> errs = errors(doc);
        assertTrue(errs.contains("arrivals[1] (A).qty는 0 이상"), errs::toString);
        assertTrue(errs.contains("arrivals[2] (B).work.hours는 0 이상"), errs::toString);
        assertTrue(errs.contains("arrivals[3] (C).work.rate_per_h는 0보다 커야 함"), errs::toString);
        assertTrue(errs.contains("arrivals[4] (F).work.by_berth.#8는 0보다 커야 함"), errs::toString);
    }

    @Test
    void missingQtyIsAWarningNotAnError() throws IOException {
        ObjectNode doc = example();
        arrival(doc, 0).remove("qty");
        CaseParser.Parsed p = CaseParser.parse(doc, rules);
        assertTrue(p.ok(), p.errors()::toString);
        assertTrue(p.warnings().contains("A: qty 없음 → 물량 0, 작업시간 0으로 계산"), p.warnings()::toString);

        ((ObjectNode) arrival(doc, 0).get("work")).put("hours", 12); // 작업시간을 주면 물량이 없어도 된다
        assertTrue(CaseParser.parse(doc, rules).warnings().stream().noneMatch(w -> w.startsWith("A: qty")));
    }

    @Test
    void currentPlanIsKeptForTheVerifier() throws IOException {
        JsonNode req = Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/SAMPLE-W46.request.json"));
        CaseParser.Parsed p = CaseParser.parse(req, rules);
        assertTrue(p.ok(), p.errors()::toString);
        JsonNode first = req.get("current_plan").get(0);
        CaseData.CurrentPlan cp = p.data().currentPlan().get(first.get("id").asString());
        assertEquals(first.get("berth").asString(), cp.berth());
        assertEquals(Times.parse(first.get("etb").asString()), cp.etb());
        assertEquals(req.get("current_plan").size(), p.data().currentPlan().size());
    }

    @Test
    void engineOptionsAreRangeChecked() throws IOException {
        ObjectNode doc = example();
        ObjectNode opts = doc.putObject("options");
        opts.put("generation", "GRID");
        opts.put("grid_min", -30); // 엔진의 눈금 반복이 끝나지 않는 값
        opts.put("max_wait_h", -1);
        List<String> errs = errors(doc);
        assertTrue(errs.stream().anyMatch(e -> e.startsWith("options.grid_min는 정수 5.0~240.0")), errs::toString);
        assertTrue(errs.stream().anyMatch(e -> e.startsWith("options.max_wait_h는 0.0~720.0")), errs::toString);
        opts.put("grid_min", 30);
        opts.put("max_wait_h", 120);
        opts.put("generation", "FAST");
        assertTrue(errors(doc).stream().anyMatch(e -> e.startsWith("options.generation은 auto·EXACT·GRID 중 하나")));
    }

    @Test
    void blankQtyIsAnErrorButMissingQtyIsAWarning() throws IOException {
        ObjectNode doc = example();
        arrival(doc, 0).putNull("qty");
        assertTrue(errors(doc).contains("arrivals[1] (A).qty가 비어 있음 (없으면 칸을 빼고, 물량이 0이면 0)"));
        ObjectNode doc2 = example();
        arrival(doc2, 0).remove("qty");
        ((ObjectNode) arrival(doc2, 0).get("work")).removeAll();
        ((ObjectNode) arrival(doc2, 0).get("work")).put("hours", 10);
        CaseParser.Parsed p = CaseParser.parse(doc2, rules);
        assertTrue(p.ok(), p.errors()::toString); // 작업시간을 주면 물량이 없어도 된다
    }

    @Test
    void currentPlanOfAFixedVesselMustEqualItsFix() throws IOException {
        ObjectNode doc = example(); // F는 FIX #8 2026-11-12T08:00
        ArrayNode cur = doc.putArray("current_plan");
        cur.addObject().put("id", "F").put("berth", "#7").put("etb", "2026-11-12T08:00");
        List<String> errs = errors(doc);
        assertTrue(errs.contains("current_plan[1]: F는 FIX라 fix와 같은 부두·ETB여야 함 (fix #8 2026-11-12T08:00)"), errs::toString);
    }
}
