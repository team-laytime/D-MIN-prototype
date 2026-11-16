package com.dmin.laytime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import tools.jackson.databind.JsonNode;

/**
 * 같은 입력이면 Spring 계산 모듈(Java)과 Python 엔진이 같은 시각·같은 센트를 내야 한다.
 * 정답은 docs/milp/ppt/out의 응답 JSON(Python 엔진이 낸 값, 손계산·전수 탐색으로 검산된 것)이다.
 * TEAM-CPSAT-*는 팀 엔진(팀원 코드 berth_sim)이 팀 해석으로 낸 응답, PPT-MILP-TEAM-*는 같은 데이터를 기존 엔진이 팀 해석으로 푼 응답
 * (agent/tests/make_team_golden.py가 만든다) — 팀원 식과 Java 식이 1분·1센트까지 같다는 증거다.
 * 하나라도 다르면 빌드가 멈춘다 — Dockerfile이 이미지를 만들기 전에 이 테스트를 돌린다.
 */
class GoldenCrossCheckTest {

    @ParameterizedTest
    @ValueSource(strings = {"EXAMPLE-3", "SAMPLE-W46", "SAMPLE-W46-WX", "TEAM-CPSAT-EXAMPLE-3", "TEAM-CPSAT-TEAM-W46", "PPT-MILP-TEAM-W46"})
    void springRecomputesEverySolverScheduleToTheCent(String name) throws IOException {
        JsonNode request = Rules.JSON.readTree(read("/golden/" + name + ".request.json"));
        JsonNode response = Rules.JSON.readTree(read("/golden/" + name + ".response.json"));
        Rules rules = Rules.bundled(patch(request));
        CaseParser.Parsed parsed = CaseParser.parse(request, rules);
        assertTrue(parsed.ok(), () -> "입력 검사 실패: " + parsed.errors());

        List<SolverOutput.Schedule> schedules = SolverOutput.schedules(response);
        assertTrue(schedules.size() >= 2 && schedules.stream().anyMatch(x -> x.rank() > 0), "기준안 + 후보 1개 이상");
        for (SolverOutput.Schedule s : schedules) {
            Verifier.Result r = Verifier.check(s.name(), rules, parsed.data(), s.plans(), s.totalCents(), s.violations(),
                    s.requireClean(), s.current() ? parsed.data().currentPlan() : null); // RunWorker와 같은 호출
            assertTrue(r.mismatches().isEmpty(), () -> name + " " + s.name() + " 불일치: " + r.mismatches());
            assertEquals(s.violations(), r.springViolations().size(),
                    () -> name + " " + s.name() + " 위반 수가 다름: " + r.springViolations());
            assertTrue(r.pass(), () -> name + " " + s.name() + " 통과 못 함");
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> patch(JsonNode request) {
        JsonNode p = request.get("rule_patch");
        return p == null || p.isNull() ? Map.of() : Rules.JSON.treeToValue(p, Map.class);
    }

    static String read(String path) throws IOException {
        try (InputStream in = GoldenCrossCheckTest.class.getResourceAsStream(path)) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
