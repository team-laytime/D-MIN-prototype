package com.dmin.laytime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.IOException;
import java.util.List;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.node.ObjectNode;

/** 솔버 응답이 계약과 다른 모양이면 NPE·0으로 넘어가지 않고 어디에 무엇이 없는지 알려 준다. */
class SolverOutputShapeTest {

    private static ObjectNode response(String name) throws IOException {
        return (ObjectNode) Rules.JSON.readTree(GoldenCrossCheckTest.read("/golden/" + name + ".response.json"));
    }

    private static ObjectNode candidate(ObjectNode resp, int i) {
        return (ObjectNode) resp.get("candidates").get(i);
    }

    private static String error(ObjectNode resp) {
        return assertThrows(IllegalArgumentException.class, () -> SolverOutput.schedules(resp)).getMessage();
    }

    @Test
    void missingRankIsAnError() throws IOException {
        ObjectNode resp = response("EXAMPLE-3");
        candidate(resp, 0).remove("rank");
        assertEquals("솔버 응답: candidates[1]에 rank 없음", error(resp));
    }

    @Test
    void rankMustBeAnInteger() throws IOException {
        ObjectNode text = response("EXAMPLE-3");
        candidate(text, 1).put("rank", "2");
        assertEquals("솔버 응답: candidates[2].rank는 1 이상의 정수여야 함: \"2\"", error(text));
        ObjectNode fraction = response("EXAMPLE-3");
        candidate(fraction, 1).put("rank", 1.5);
        error(fraction);
    }

    @Test
    void requiredPlanFieldsAreChecked() throws IOException {
        ObjectNode noId = response("EXAMPLE-3");
        ((ObjectNode) candidate(noId, 0).get("plans").get(0)).remove("arrival_id");
        assertEquals("솔버 응답: candidates[1].plans[1]에 arrival_id 없음", error(noId));

        ObjectNode blankBerth = response("EXAMPLE-3");
        ((ObjectNode) candidate(blankBerth, 0).get("plans").get(1)).put("berth", " ");
        assertEquals("솔버 응답: candidates[1].plans[2]에 berth 없음", error(blankBerth));

        ObjectNode noEtb = response("EXAMPLE-3");
        ((ObjectNode) noEtb.get("baseline").get("plans").get(0)).putNull("etb");
        assertEquals("솔버 응답: baseline.plans[1]에 etb 없음", error(noEtb));

        ObjectNode noMoney = response("EXAMPLE-3");
        ((ObjectNode) candidate(noMoney, 2).get("plans").get(3)).remove("demurrage_usd");
        assertEquals("솔버 응답: candidates[3].plans[4]에 demurrage_usd 없음", error(noMoney));

        ObjectNode noTotal = response("EXAMPLE-3");
        ((ObjectNode) noTotal.get("baseline")).remove("total_usd");
        assertEquals("솔버 응답: baseline에 total_usd 없음", error(noTotal));
    }

    @Test
    void plansAndViolationsMustBeArrays() throws IOException {
        ObjectNode plans = response("EXAMPLE-3");
        candidate(plans, 0).putObject("plans");
        error(plans);
        ObjectNode violations = response("EXAMPLE-3");
        candidate(violations, 0).put("violations", "없음");
        error(violations);
        ObjectNode noViolations = response("EXAMPLE-3");
        ((ObjectNode) noViolations.get("baseline")).remove("violations");
        assertEquals("솔버 응답: baseline에 violations 없음", error(noViolations));
    }

    @Test
    void onlyTheCurrentPlanIsMarkedCurrent() throws IOException {
        List<SolverOutput.Schedule> s = SolverOutput.schedules(response("SAMPLE-W46"));
        assertEquals(List.of("현행 계획"), s.stream().filter(SolverOutput.Schedule::current).map(SolverOutput.Schedule::name).toList());
        assertEquals(List.of("기준안", "1안", "2안", "3안"),
                s.stream().filter(x -> !x.current()).map(SolverOutput.Schedule::name).toList());
        assertEquals(0, SolverOutput.schedules(response("EXAMPLE-3")).stream().filter(SolverOutput.Schedule::current).count());
    }
}
