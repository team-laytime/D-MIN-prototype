package com.dmin.runs;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.dmin.cases.CaseService;
import com.dmin.laytime.Rules;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

/** 실행 지휘(INPUT → SOLVE → VERIFY → PUBLISH)를 DB·에이전트 없이 돌려 본다. 솔버 응답은 정답 EXAMPLE-3. */
class RunWorkerTest {

    private static final JsonMapper JSON = JsonMapper.builder().build();

    /** DB 대신 단계와 끝 상태를 적어 둔다. */
    static final class FakeRepo extends RunRepository {
        final List<String> calls = new ArrayList<>();
        final Map<Integer, String> stepStatus = new TreeMap<>();
        final Map<Integer, String> stepDetail = new TreeMap<>();
        String status;
        String error;
        String summary;
        String worker;
        int finishResult = 1;

        String engine = "ppt-milp";
        String profile = "ppt";

        FakeRepo() {
            super(null, null);
        }

        @Override
        Optional<RunRow> find(long id) {
            return Optional.of(new RunRow(id, 7, "EXAMPLE-3", "예시", "0123456789abcdef", 4, "RUNNING", 3, 120, engine, profile, "w", null,
                    null, null, null, null));
        }

        boolean stillOwner = true; // false면 '다른 Pod가 이미 FAILED로 정리한 실행'을 흉내 낸다

        @Override
        boolean stepStart(long runId, String worker, int seq, String name) {
            calls.add("start " + seq);
            if (!stillOwner) {
                return false;
            }
            stepStatus.put(seq, "RUNNING");
            return true;
        }

        @Override
        void stepEnd(long runId, int seq, boolean ok, String detail) {
            calls.add("end " + seq);
            if ("RUNNING".equals(stepStatus.get(seq))) {
                stepStatus.put(seq, ok ? "OK" : "FAILED");
                stepDetail.put(seq, detail);
            }
        }

        @Override
        void closeOpenSteps(long runId, String detail) {
            calls.add("close");
            for (Map.Entry<Integer, String> e : stepStatus.entrySet()) {
                if ("RUNNING".equals(e.getValue())) {
                    e.setValue("FAILED");
                    stepDetail.put(e.getKey(), detail);
                }
            }
        }

        @Override
        int finish(long runId, String worker, String status, String error, String summary, String verification, String result) {
            calls.add("finish");
            this.worker = worker;
            this.status = status;
            this.error = error;
            this.summary = summary;
            return finishResult;
        }
    }

    static final class FakeAgent extends AgentClient {
        private final String answer;

        FakeAgent(String answer) {
            super(new Props("http://agent.invalid", Duration.ofSeconds(1), Duration.ofSeconds(1)));
            this.answer = answer;
        }

        @Override
        String optimize(String caseJson, int top, int timeLimitS, String engine) {
            sentEngine = engine;
            sentRequest = caseJson;
            return answer;
        }

        String sentEngine;
        String sentRequest;
    }

    private FakeRepo repo;
    private FakeAgent agent;

    private RunWorker worker(String agentAnswer) throws IOException {
        return worker(agentAnswer, read("EXAMPLE-3.request.json"), "ppt-milp", "ppt");
    }

    private RunWorker worker(String agentAnswer, String payload, String engine, String profile) {
        CaseService cases = mock(CaseService.class); // 하위 클래스 방식(test/resources/mockito-extensions) — 에이전트를 붙이지 않는다
        when(cases.payload(7L)).thenReturn(payload);
        repo = new FakeRepo();
        repo.engine = engine;
        repo.profile = profile;
        agent = new FakeAgent(agentAnswer);
        return new RunWorker(repo, cases, agent, JSON, new RunWorker.Props(true, Duration.ofSeconds(90)));
    }

    private static String read(String name) throws IOException {
        try (InputStream in = RunWorkerTest.class.getResourceAsStream("/golden/" + name)) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    /** 정답 응답 + 에이전트(main.py)가 붙이는 규칙 표 지문. */
    private static ObjectNode answer() throws IOException {
        return answer("EXAMPLE-3");
    }

    private static ObjectNode answer(String name) throws IOException {
        ObjectNode resp = (ObjectNode) JSON.readTree(read(name + ".response.json"));
        ((ObjectNode) resp.get("engine")).put("rules_sha256", Rules.bundled().sha256());
        return resp;
    }

    private Map<String, JsonNode> rows() {
        Map<String, JsonNode> out = new LinkedHashMap<>();
        for (JsonNode r : JSON.readTree(repo.summary).get("schedules").values()) {
            out.put(r.get("name").asString(), r);
        }
        return out;
    }

    @Test
    void goodAnswerIsPublishedWithSpringNumbers() throws IOException {
        RunWorker w = worker(answer().toString());
        w.execute(1);
        assertEquals("SUCCEEDED", repo.status, repo.error);
        assertEquals(w.workerId(), repo.worker); // 이 Pod가 잡은 실행만 끝낸다
        assertEquals(Map.of(1, "OK", 2, "OK", 3, "OK", 4, "OK"), repo.stepStatus);
        assertEquals(List.of("end 4", "finish"), repo.calls.subList(repo.calls.size() - 2, repo.calls.size())); // PUBLISH를 닫고 나서 끝낸다
        JsonNode first = rows().get("1안");
        assertTrue(first.get("verified").asBoolean());
        assertEquals(7192.30, first.get("total_usd").doubleValue(), 1e-9);
        assertEquals(-18449.32, first.get("delta_vs_baseline_usd").doubleValue(), 1e-9); // Spring 금액끼리: 7,192.30 − 25,641.62
        assertEquals(2, first.get("changes").asInt());
        assertEquals("OPTIMAL", first.get("status").asString());
        assertTrue(rows().get("기준안").get("verified").asBoolean());
    }

    @Test
    void missingOrDifferentRulesFingerprintFailsClosed() throws IOException {
        ObjectNode none = answer();
        ((ObjectNode) none.get("engine")).remove("rules_sha256");
        worker(none.toString()).execute(1);
        assertEquals("FAILED", repo.status);
        assertEquals("FAILED", repo.stepStatus.get(3));
        assertTrue(repo.stepDetail.get(3).contains("에이전트 응답에 규칙 표 지문 없음"), repo.stepDetail.get(3));
        assertTrue(rows().values().stream().noneMatch(r -> r.get("verified").asBoolean()));

        ObjectNode other = answer();
        ((ObjectNode) other.get("engine")).put("rules_sha256", "0".repeat(64));
        worker(other.toString()).execute(2);
        assertEquals("FAILED", repo.status);
        assertTrue(repo.stepDetail.get(3).contains("규칙 표가 다름"), repo.stepDetail.get(3));
    }

    @Test
    void candidatesAreMatchedByRankNotByPosition() throws IOException {
        ObjectNode resp = answer();
        ArrayNode cands = (ArrayNode) resp.get("candidates");
        ((ObjectNode) cands.get(2)).put("status", "TIME_LIMIT"); // 3안만 시간 제한으로 끝난 것으로
        ArrayNode reversed = JSON.createArrayNode();
        for (int i = cands.size() - 1; i >= 0; i--) {
            reversed.add(cands.get(i));
        }
        resp.set("candidates", reversed); // 배열 순서: 3안, 2안, 1안
        worker(resp.toString()).execute(1);
        assertEquals("SUCCEEDED", repo.status, repo.error);
        assertEquals("OPTIMAL", rows().get("1안").get("status").asString());
        assertEquals("TIME_LIMIT", rows().get("3안").get("status").asString());
    }

    @Test
    void badAnswerShapeFailsTheRunAtVerify() throws IOException {
        ObjectNode resp = answer();
        ((ObjectNode) resp.get("candidates").get(0)).remove("rank");
        worker(resp.toString()).execute(1);
        assertEquals("FAILED", repo.status);
        assertEquals("솔버 응답 모양이 다름: 솔버 응답: candidates[1]에 rank 없음", repo.error);
        assertEquals("FAILED", repo.stepStatus.get(3));
        assertEquals("솔버 응답: candidates[1]에 rank 없음", repo.stepDetail.get(3));
        assertFalse(repo.stepStatus.containsKey(4));
    }

    @Test
    void unexpectedErrorClosesTheOpenStep() throws IOException {
        worker("JSON이 아닌 응답").execute(1);
        assertEquals("FAILED", repo.status);
        assertTrue(repo.error.startsWith("서버 오류: "), repo.error);
        assertEquals("FAILED", repo.stepStatus.get(2)); // SOLVE가 '진행 중'으로 남지 않는다
        assertEquals(repo.error, repo.stepDetail.get(2));
        assertEquals(List.of("close", "finish"), repo.calls.subList(repo.calls.size() - 2, repo.calls.size()));
    }

    @Test
    void runAlreadyClosedByAnotherPodIsLeftAlone() throws IOException {
        RunWorker w = worker(answer().toString());
        repo.finishResult = 0; // 맥박 끊김으로 다른 Pod가 이미 FAILED로 바꾼 실행
        assertDoesNotThrow(() -> w.execute(1));
        assertEquals("finish", repo.calls.getLast());
    }

    @Test
    void takenOverRunStopsWithoutOpeningSteps() throws IOException {
        RunWorker w = worker(answer().toString());
        repo.stillOwner = false; // 맥박이 끊겨 다른 Pod가 이미 FAILED로 정리함
        w.execute(1);
        assertEquals(List.of("start 1"), repo.calls); // 단계도, 끝 상태도 쓰지 않는다
        assertTrue(repo.stepStatus.isEmpty());
    }

    @Test
    void storedRulePatchThatNoLongerExistsFailsAtInput() throws IOException {
        CaseService cases = mock(CaseService.class);
        ObjectNode req = (ObjectNode) JSON.readTree(read("EXAMPLE-3.request.json"));
        req.putObject("rule_patch").put("demurrage.weather_basiss", "WAIT"); // 오타 경로 (S8 전에 저장된 데이터라고 가정)
        when(cases.payload(7L)).thenReturn(req.toString());
        repo = new FakeRepo();
        new RunWorker(repo, cases, new FakeAgent(answer().toString()), JSON, new RunWorker.Props(true, Duration.ofSeconds(90))).execute(1);
        assertEquals("FAILED", repo.status);
        assertTrue(repo.error.startsWith("입력 검사 실패: rule_patch 경로 없음"), repo.error);
        assertEquals("FAILED", repo.stepStatus.get(1));
    }

    @Test
    void teamEngineGetsTheTeamInterpretationAndIsVerifiedWithIt() throws IOException {
        // 팀 엔진(팀원 코드)은 팀 해석으로만 돈다: Spring이 해석 patch를 덮어 보내고, 재검증도 같은 규칙으로 한다
        worker(answer("TEAM-CPSAT-EXAMPLE-3").toString(), read("EXAMPLE-3.request.json"), "team-cpsat", "team").execute(1);
        assertEquals("SUCCEEDED", repo.status, repo.error);
        assertEquals("team-cpsat", agent.sentEngine);
        JsonNode sent = JSON.readTree(agent.sentRequest).get("rule_patch");
        assertEquals("DEMURRAGE", sent.get("demurrage.weather_basis").asString());
        assertEquals("SUBJECT", sent.get("night_pilotage.dawn.scope").asString());
        assertEquals(9252.07, rows().get("1안").get("total_usd").doubleValue(), 1e-9);
        JsonNode summary = JSON.readTree(repo.summary);
        assertEquals("team-cpsat", summary.get("run_engine").asString());
        assertEquals("team", summary.get("profile").get("name").asString());
        assertTrue(repo.stepDetail.get(1).contains("팀원 코드"), repo.stepDetail.get(1));
    }

    @Test
    void sameTeamAnswerFailsUnderTheOldInterpretation() throws IOException {
        // 같은 팀 엔진 응답을 기존 해석으로 다시 계산하면 맞지 않는다 → 해석이 다르면 통과시키지 않는다(fail closed)
        worker(answer("TEAM-CPSAT-EXAMPLE-3").toString(), read("EXAMPLE-3.request.json"), "ppt-milp", "ppt").execute(1);
        assertEquals("FAILED", repo.status, repo.error);
    }

    @Test
    void dataWeatherOptionThatContradictsTheProfileFailsAtInput() throws IOException {
        ObjectNode req = (ObjectNode) JSON.readTree(read("EXAMPLE-3.request.json"));
        req.putObject("options").put("weather_basis", "USED");
        worker(answer().toString(), req.toString(), "team-cpsat", "team").execute(1);
        assertEquals("FAILED", repo.status);
        assertTrue(repo.error.contains("options.weather_basis(USED)"), repo.error);
        assertEquals(null, agent.sentEngine); // 에이전트를 부르지 않는다
    }

    @Test
    void noSolutionIsReportedAsTimeNotAsInfeasible() throws IOException {
        ObjectNode resp = answer();
        resp.put("status", "NO_SOLUTION");
        resp.putArray("candidates");
        worker(resp.toString()).execute(1);
        assertEquals("FAILED", repo.status);
        assertTrue(repo.error.startsWith("제한 시간 안에 해를 못 찾음"), repo.error);
    }
}
