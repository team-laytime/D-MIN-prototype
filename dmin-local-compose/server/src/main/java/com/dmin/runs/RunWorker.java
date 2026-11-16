package com.dmin.runs;

import com.dmin.laytime.CaseData;
import com.dmin.laytime.CaseParser;
import com.dmin.laytime.Rules;
import com.dmin.laytime.SolverOutput;
import com.dmin.laytime.Verifier;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ObjectNode;

/**
 * 실행 지휘 (정의서 CMP-06). 대기 중인 실행을 하나 집어 고정된 순서로 돌린다.
 * <pre>
 * 1 INPUT    저장된 입력을 Spring 계산 모듈로 다시 읽는다
 * 2 SOLVE    Python 에이전트 POST /v1/optimize — 엔진은 실행마다 고른다: team-cpsat(팀원 코드 berth_sim, CP-SAT) · ppt-milp(기존, HiGHS).
 *            규칙 해석(profile)의 patch를 데이터의 rule_patch 위에 덮어 보내고, 3단계도 같은 규칙으로 다시 계산한다
 * 3 VERIFY   솔버가 낸 일정마다 Spring이 PPT 식으로 처음부터 다시 계산 — 1분·1센트라도 다르거나 규칙 표 지문이 같지 않으면 그 후보는 실패
 * 4 PUBLISH  후보를 모두 결과에 싣되, 재검증에 실패한 후보는 '실패'로 표시되고 고를 수 없다(결정 API가 막는다).
 *            상태 SUCCEEDED · PARTIAL(일부만 통과) · FAILED
 * </pre>
 * 인스턴스가 여러 개여도 같은 실행을 두 번 집지 않는다(SKIP LOCKED). 실행 중에는 10초마다 맥박을 남긴다 — 맥박은 스케줄러 풀의
 * 다른 스레드에서 돌아 계산이 poll 스레드를 붙잡고 있어도 멈추지 않는다(application.yml spring.task.scheduling.pool.size).
 * 맥박이 끊긴 실행은 다른 인스턴스가 FAILED로 바꾼다(인스턴스가 죽어도 '실행 중'으로 남지 않는다).
 * 끝낼 때는 이 인스턴스가 잡고 있는 RUNNING 실행만 바꾼다. 이미 다른 인스턴스가 끝낸 실행은 덮어쓰지 않는다.
 */
@Component
class RunWorker {

    private static final Logger log = LoggerFactory.getLogger(RunWorker.class);

    @ConfigurationProperties("dmin.runs")
    record Props(@DefaultValue("true") boolean workerEnabled, @DefaultValue("90s") Duration staleAfter) {}

    private final RunRepository repo;
    private final com.dmin.cases.CaseService cases;
    private final AgentClient agent;
    private final ObjectMapper json;
    private final Props props;
    private final String workerId;
    private final AtomicLong current = new AtomicLong(0);

    RunWorker(RunRepository repo, com.dmin.cases.CaseService cases, AgentClient agent, ObjectMapper json, Props props) {
        this.repo = repo;
        this.cases = cases;
        this.agent = agent;
        this.json = json;
        this.props = props;
        String host = System.getenv("HOSTNAME");
        this.workerId = host == null || host.isBlank() ? "local" : host;
    }

    String workerId() {
        return workerId;
    }

    @Scheduled(fixedDelayString = "${dmin.runs.poll-ms:2000}", initialDelayString = "${dmin.runs.initial-delay-ms:5000}")
    void poll() {
        if (!props.workerEnabled()) {
            return;
        }
        try {
            int stale = repo.failStale(props.staleAfter());
            if (stale > 0) {
                log.warn("맥박이 끊긴 실행 {}건을 FAILED로 바꿈", stale);
            }
            Optional<Long> next = repo.claimNext(workerId);
            next.ifPresent(this::execute);
        } catch (RuntimeException e) {
            log.warn("작업 큐 확인 실패: {}", e.getMessage());
        }
    }

    @Scheduled(fixedDelayString = "${dmin.runs.heartbeat-ms:10000}")
    void heartbeat() {
        long id = current.get();
        if (id != 0) {
            try {
                repo.heartbeat(id);
            } catch (RuntimeException e) {
                log.warn("맥박 기록 실패 run={}: {}", id, e.getMessage());
            }
        }
    }

    void execute(long runId) {
        current.set(runId);
        long t0 = System.nanoTime();
        log.info("실행 {} 시작 (worker {})", runId, workerId);
        try {
            RunRepository.RunRow run = repo.find(runId).orElseThrow();
            String payload = cases.payload(run.caseId());
            JsonNode request = json.readTree(payload);

            // 1 INPUT
            if (!open(runId, 1, "INPUT")) {
                return;
            }
            Rules rules;
            Map<String, Object> patch;
            try {
                patch = Rules.profilePatch(run.profile(), casePatch(request)); // 실행할 때 고른 해석이 데이터의 rule_patch보다 앞선다
                rules = Rules.bundled(patch);
            } catch (IllegalArgumentException e) { // 예전에 저장된 데이터의 rule_patch가 지금 규칙 표에 없는 경로일 때 · 없는 해석
                repo.stepEnd(runId, 1, false, e.getMessage());
                finish(runId, "FAILED", "입력 검사 실패: " + e.getMessage(), null, null, null);
                return;
            }
            JsonNode optBasis = request.path("options").path("weather_basis");
            if (!"ppt".equals(run.profile()) && optBasis.isString() && !optBasis.asString().equals(rules.weatherBasis())) {
                String why = "데이터의 options.weather_basis(" + optBasis.asString() + ")가 고른 해석 '" + Rules.profileTitle(run.profile())
                        + "'의 기상체선 구간(" + rules.weatherBasis() + ")과 다름 — 데이터에서 그 칸을 빼고 다시";
                repo.stepEnd(runId, 1, false, why);
                finish(runId, "FAILED", "입력 검사 실패: " + why, null, null, null);
                return;
            }
            CaseParser.Parsed parsed = CaseParser.parse(request, rules);
            if (!parsed.ok()) {
                repo.stepEnd(runId, 1, false, String.join("\n", parsed.errors()));
                finish(runId, "FAILED", "입력 검사 실패", null, null, null);
                return;
            }
            CaseData cs = parsed.data();
            repo.stepEnd(runId, 1, true, "입항 건 " + cs.arrivals().size() + " · 규칙 " + rules.version() + " · 해석 "
                    + Rules.profileTitle(run.profile()) + " · 엔진 " + engineTitle(run.engine()));

            // 2 SOLVE
            if (!open(runId, 2, "SOLVE")) {
                return;
            }
            long s0 = System.nanoTime();
            String raw;
            try {
                raw = agent.optimize(withPatch(request, patch), run.top(), run.timeLimit(), run.engine());
            } catch (AgentClient.AgentException e) {
                log.warn("실행 {}: 에이전트 호출 실패 — {}", runId, e.getMessage()); // 에이전트는 접근 로그를 끄고 돌아서 원인은 여기 남긴다
                repo.stepEnd(runId, 2, false, e.getMessage());
                finish(runId, "FAILED", e.getMessage(), null, null, null);
                return;
            }
            JsonNode resp = json.readTree(raw);
            double solveS = (System.nanoTime() - s0) / 1e9;
            String engineStatus = resp.path("status").asString("?");
            repo.stepEnd(runId, 2, true, String.format("엔진 %s · 상태 %s · 후보 %d개 · %.1f초",
                    resp.path("engine").path("version").asString("?"), engineStatus, resp.path("candidates").size(), solveS));

            // 3 VERIFY
            if (!open(runId, 3, "VERIFY")) {
                return;
            }
            long v0 = System.nanoTime();
            List<SolverOutput.Schedule> given;
            try {
                given = SolverOutput.schedules(resp);
            } catch (IllegalArgumentException e) {
                repo.stepEnd(runId, 3, false, e.getMessage());
                finish(runId, "FAILED", "솔버 응답 모양이 다름: " + e.getMessage(), null, null, null);
                return;
            }
            List<Map<String, Object>> checks = new ArrayList<>();
            int checkedPlans = 0;
            int mismatches = 0;
            int passedCandidates = 0;
            int candidates = 0;
            String agentRulesSha = resp.path("engine").path("rules_sha256").asString("");
            // 지문이 없거나 다르면 같은 규칙 표로 풀었는지 알 수 없다 → 통과시키지 않는다(fail closed)
            boolean rulesSame = !agentRulesSha.isEmpty() && agentRulesSha.equals(Rules.bundled().sha256());
            String rulesNote = rulesSame ? "규칙 표 같음" : agentRulesSha.isEmpty() ? "에이전트 응답에 규칙 표 지문 없음" : "규칙 표가 다름";
            List<Verifier.Result> results = new ArrayList<>();
            Verifier.Result baseline = null;
            for (SolverOutput.Schedule s : given) {
                // 현행 계획은 요청의 current_plan(사람이 짠 부두·ETB)을 그대로 계산했는지도 본다
                Verifier.Result r = Verifier.check(s.name(), rules, cs, s.plans(), s.totalCents(), s.violations(), s.requireClean(),
                        s.current() ? cs.currentPlan() : null);
                results.add(r);
                if (s.rank() == 0 && !s.current()) {
                    baseline = r;
                }
                checkedPlans += r.plans();
                mismatches += r.mismatches().size();
                if (s.rank() > 0) {
                    candidates++;
                    if (r.pass() && rulesSame) {
                        passedCandidates++;
                    }
                }
                Map<String, Object> c = new LinkedHashMap<>();
                c.put("name", s.name());
                c.put("rank", s.rank());
                c.put("pass", r.pass() && rulesSame);
                c.put("solver_total_usd", r.solverCents() / 100.0);
                c.put("spring_total_usd", r.springCents() / 100.0);
                c.put("solver_violations", r.solverViolations());
                c.put("spring_violations", r.springViolations());
                c.put("mismatches", r.mismatches());
                checks.add(c);
            }
            List<Map<String, Object>> schedules = new ArrayList<>();
            for (int i = 0; i < given.size(); i++) {
                schedules.add(summaryRow(given.get(i), results.get(i), baseline, rulesSame, resp));
            }
            double verifyMs = (System.nanoTime() - v0) / 1e6;
            Map<String, Object> verification = new LinkedHashMap<>();
            verification.put("checked_plans", checkedPlans);
            verification.put("mismatches", mismatches);
            verification.put("rules_same", rulesSame);
            verification.put("spring_rules", rules.version() + " " + Rules.bundled().sha256().substring(0, 12));
            verification.put("agent_rules", resp.path("engine").path("rules_version").asString("?") + " "
                    + (agentRulesSha.length() >= 12 ? agentRulesSha.substring(0, 12) : "?"));
            verification.put("schedules", checks);
            repo.stepEnd(runId, 3, mismatches == 0 && rulesSame, String.format(
                    "일정 %d개 · 작업계획 %d개를 Spring이 다시 계산 · 불일치 %d · %s · %.0fms",
                    checks.size(), checkedPlans, mismatches, rulesNote, verifyMs));

            // 4 PUBLISH
            if (!open(runId, 4, "PUBLISH")) {
                return;
            }
            String status;
            String error = null;
            if ("INFEASIBLE".equals(engineStatus)) {
                status = "SUCCEEDED";
                error = "실행 가능한 후보 없음 (모든 제약을 지키는 조합이 없음, FR-43)";
            } else if ("NO_SOLUTION".equals(engineStatus)) {
                status = "FAILED";
                error = "제한 시간 안에 해를 못 찾음 — 불가능하다는 뜻은 아님, 제한 시간을 늘려 다시";
            } else if (candidates > 0 && passedCandidates == candidates) {
                status = "SUCCEEDED";
            } else if (passedCandidates > 0) {
                status = "PARTIAL";
                error = "후보 " + candidates + "개 중 " + passedCandidates + "개만 재검증 통과";
            } else {
                status = "FAILED";
                error = "재검증을 통과한 후보가 없음";
            }
            Map<String, Object> summary = new LinkedHashMap<>();
            summary.put("engine", json.treeToValue(resp.path("engine"), Map.class));
            summary.put("run_engine", run.engine());
            summary.put("profile", Map.of("name", run.profile(), "title", Rules.profileTitle(run.profile()),
                    "patch", Rules.profilePatch(run.profile(), Map.of())));
            summary.put("notes", json.treeToValue(resp.path("notes"), List.class));
            summary.put("engine_status", engineStatus);
            summary.put("request_hash", resp.path("request_hash").asString(null));
            summary.put("plan_window", json.treeToValue(resp.path("plan_window"), Map.class));
            summary.put("schedules", schedules);
            summary.put("verified_candidates", passedCandidates);
            summary.put("candidates", candidates);
            summary.put("solve_seconds", Math.round(solveS * 10) / 10.0);
            summary.put("verify_ms", Math.round(verifyMs));
            summary.put("components", json.treeToValue(resp.path("components"), List.class));
            String summaryJson = json.writeValueAsString(summary);
            String verificationJson = json.writeValueAsString(verification);
            // 단계를 먼저 닫는다: 실행이 끝난 것으로 보이는 순간에 PUBLISH가 아직 '진행 중'이면 안 된다
            repo.stepEnd(runId, 4, !"FAILED".equals(status), status + (error == null ? "" : " — " + error));
            finish(runId, status, error, summaryJson, verificationJson, raw);
            log.info("실행 {} 끝: {} ({}초)", runId, status, Math.round((System.nanoTime() - t0) / 1e9));
        } catch (RuntimeException e) {
            log.error("실행 {} 실패", runId, e);
            String error = "서버 오류: " + e.getClass().getSimpleName() + " " + e.getMessage();
            repo.closeOpenSteps(runId, error); // 도중에 멈춘 단계가 '진행 중'으로 남지 않게
            finish(runId, "FAILED", error, null, null, null);
        } finally {
            current.set(0);
        }
    }

    /** 이 인스턴스가 잡고 있는 실행만 끝낸다. 0건이면 다른 인스턴스가 이미 끝낸 실행(맥박 끊김 등)이라 그대로 둔다. */
    private void finish(long runId, String status, String error, String summary, String verification, String result) {
        if (repo.finish(runId, workerId, status, error, summary, verification, result) == 0) {
            log.warn("실행 {}: 이미 다른 인스턴스가 끝낸 실행 — 덮어쓰지 않음 (이 인스턴스 결과 {})", runId, status);
        }
    }

    private Map<String, Object> summaryRow(
            SolverOutput.Schedule s, Verifier.Result r, Verifier.Result baseline, boolean rulesSame, JsonNode resp) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("name", s.name());
        m.put("rank", s.rank());
        m.put("total_usd", r.springCents() / 100.0); // 화면에 내는 금액은 Spring이 다시 계산한 값
        m.put("violations", r.springViolations().size());
        m.put("verified", r.pass() && rulesSame); // 결정 API가 고를 수 있게 하는 조건(verification.schedules[].pass)과 같다
        if (s.rank() > 0) {
            JsonNode c = candidate(resp, s.rank()); // 배열 순서가 아니라 rank 값으로 찾는다
            // status(OPTIMAL·TIME_LIMIT)와 changes(기준안 대비 바꾼 배 수)는 솔버 쪽 정보다. Spring이 다시 계산하지 않는다.
            m.put("status", c == null ? null : c.path("status").asString(""));
            // 기준안 대비 차이는 Spring이 다시 계산한 금액끼리 뺀다
            m.put("delta_vs_baseline_usd", baseline == null ? null : (r.springCents() - baseline.springCents()) / 100.0);
            m.put("changes", c == null ? null : c.path("changes_vs_baseline").size());
        }
        return m;
    }

    private static JsonNode candidate(JsonNode resp, int rank) {
        for (JsonNode c : resp.path("candidates").values()) {
            if (c.path("rank").isIntegralNumber() && c.path("rank").asInt() == rank) {
                return c;
            }
        }
        return null;
    }

    /** 단계를 연다. 맥박이 끊겨 다른 인스턴스가 이 실행을 이미 FAILED로 정리했으면 열지 않고 여기서 멈춘다. */
    private boolean open(long runId, int seq, String name) {
        if (repo.stepStart(runId, workerId, seq, name)) {
            return true;
        }
        log.warn("실행 {}: {} 단계를 열지 못함 — 이미 다른 인스턴스가 끝낸 실행이라 여기서 멈춤", runId, name);
        return false;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> casePatch(JsonNode request) {
        JsonNode p = request.get("rule_patch");
        return p == null || p.isNull() ? Map.of() : json.treeToValue(p, Map.class);
    }

    /** 에이전트에 보낼 요청: 데이터 그대로 + rule_patch만 '데이터 patch + 고른 해석' 결과로 바꾼다. */
    private String withPatch(JsonNode request, Map<String, Object> patch) {
        ObjectNode copy = (ObjectNode) request.deepCopy();
        if (patch.isEmpty()) {
            copy.remove("rule_patch");
        } else {
            copy.set("rule_patch", json.valueToTree(patch));
        }
        return json.writeValueAsString(copy);
    }

    static String engineTitle(String engine) {
        return "team-cpsat".equals(engine) ? "팀 엔진(팀원 코드 berth_sim · CP-SAT)" : "기존 엔진(HiGHS)";
    }
}
