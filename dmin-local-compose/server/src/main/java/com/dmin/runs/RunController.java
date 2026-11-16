package com.dmin.runs;

import com.dmin.cases.CaseService;
import com.dmin.common.error.DminException;
import com.dmin.common.error.ErrorCode;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import com.dmin.laytime.Rules;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.ObjectMapper;

/**
 * 실행 접수와 결과 (정의서 5.3 대표 API: POST /runs · GET /runs/{id} · /candidates · /decisions).
 * 접수는 바로 202 + run_id로 돌려준다. 계산은 RunWorker가 한다. 화면은 GET /runs/{id}로 상태를 본다.
 */
@RestController
class RunController {

    /**
     * engine  team-cpsat = 팀 엔진(팀원 코드 berth_sim, CP-SAT) · ppt-milp = 기존 엔진(HiGHS). 비우면 dmin.runs.defaults.engine
     * profile 규칙 해석(rules/terminal.json profiles). 비우면 팀 엔진은 team, 기존 엔진은 ppt. 팀 엔진은 team으로만 돈다
     */
    record CreateRun(
            @JsonProperty("case_id") @NotNull Long caseId,
            @Min(1) @Max(5) Integer top,
            @JsonProperty("time_limit_s") @Min(10) @Max(600) Integer timeLimitS,
            @Pattern(regexp = "team-cpsat|ppt-milp") String engine,
            @Size(max = 40) String profile) {}

    /** 실행 기본값 (application.yml dmin.runs.defaults). */
    @ConfigurationProperties("dmin.runs.defaults")
    record Defaults(@DefaultValue("team-cpsat") String engine) {}

    record Decision(
            @NotNull @Min(1) @Max(5) Integer rank,
            @NotBlank @Pattern(regexp = "SELECT|CANCEL") String action,
            @NotBlank @Size(max = 60) String actor,
            @Size(max = 500) String reason) {}

    private final RunRepository repo;
    private final CaseService cases;
    private final ObjectMapper json;
    private final Defaults defaults;

    RunController(RunRepository repo, CaseService cases, ObjectMapper json, Defaults defaults) {
        this.repo = repo;
        this.cases = cases;
        this.json = json;
        this.defaults = defaults;
    }

    @PostMapping("/runs")
    ResponseEntity<Map<String, Object>> create(@Valid @RequestBody CreateRun body) {
        cases.get(body.caseId(), false); // 없으면 404
        int top = body.top() == null ? 3 : body.top();
        int limit = body.timeLimitS() == null ? 120 : body.timeLimitS();
        String engine = body.engine() == null || body.engine().isBlank() ? defaults.engine() : body.engine();
        String profile = body.profile() == null || body.profile().isBlank()
                ? ("team-cpsat".equals(engine) ? "team" : "ppt")
                : body.profile();
        if (!Rules.profileNames().contains(profile)) {
            throw new DminException(ErrorCode.VALIDATION, "없는 규칙 해석: " + profile + " (있는 것: " + Rules.profileNames() + ")");
        }
        if ("team-cpsat".equals(engine) && !"team".equals(profile)) {
            throw new DminException(ErrorCode.VALIDATION, "팀 엔진(팀원 코드)은 규칙 해석 team으로만 돈다 — 코드에 해석이 고정돼 있음");
        }
        // 같은 데이터·같은 설정으로 이미 대기·실행 중인 실행이 있으면 그것을 돌려준다(중복 요청 키).
        // 확인과 넣기는 한 트랜잭션 + 데이터별 잠금이라 두 요청이 동시에 와도 하나만 생긴다.
        RunRepository.Created run = repo.createIfNotActive(body.caseId(), top, limit, engine, profile);
        if (run.duplicate()) {
            return ResponseEntity.ok(Map.of("run_id", run.id(), "status", "ALREADY_ACTIVE", "duplicate", true));
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of("run_id", run.id(), "status", "QUEUED", "duplicate", false));
    }

    @GetMapping("/runs")
    List<Map<String, Object>> list(@RequestParam(defaultValue = "30") int limit) {
        return repo.list(Math.clamp(limit, 1, 200)).stream().map(this::view).toList();
    }

    @GetMapping("/runs/{id}")
    Map<String, Object> get(@PathVariable long id) {
        RunRepository.RunRow r = repo.find(id).orElseThrow(() -> new DminException(ErrorCode.NOT_FOUND, "실행 " + id + " 없음"));
        Map<String, Object> v = view(r);
        v.put("steps", repo.steps(id));
        String verification = repo.json(id, "verification");
        v.put("verification", verification == null ? null : json.readValue(verification, Map.class));
        v.put("decisions", repo.decisions(id));
        return v;
    }

    /** 솔버 응답 JSON 원본(산출 근거 trace 포함). scripts/dmin-data.py가 쓴다(화면은 부르지 않는다). */
    @GetMapping(path = "/runs/{id}/result", produces = MediaType.APPLICATION_JSON_VALUE)
    String result(@PathVariable long id) {
        repo.find(id).orElseThrow(() -> new DminException(ErrorCode.NOT_FOUND, "실행 " + id + " 없음"));
        String r = repo.json(id, "result");
        if (r == null) {
            throw new DminException(ErrorCode.NOT_FOUND, "실행 " + id + "의 결과가 아직 없음");
        }
        return r;
    }

    @PostMapping("/runs/{id}/decisions")
    ResponseEntity<Map<String, Object>> decide(@PathVariable long id, @Valid @RequestBody Decision body) {
        RunRepository.RunRow r = repo.find(id).orElseThrow(() -> new DminException(ErrorCode.NOT_FOUND, "실행 " + id + " 없음"));
        if (!List.of("SUCCEEDED", "PARTIAL").contains(r.status())) {
            throw new DminException(ErrorCode.CONFLICT, "끝난 실행(SUCCEEDED·PARTIAL)의 후보만 고를 수 있음: 지금 " + r.status());
        }
        String verification = repo.json(id, "verification");
        boolean verified = false;
        if (verification != null) {
            for (Object o : (List<?>) json.readValue(verification, Map.class).get("schedules")) {
                Map<?, ?> m = (Map<?, ?>) o;
                if (body.rank().equals(m.get("rank")) && Boolean.TRUE.equals(m.get("pass"))) {
                    verified = true;
                }
            }
        }
        if (!verified) { // 재검증을 통과하지 못한 후보는 확정 대상이 아니다
            throw new DminException(ErrorCode.CONFLICT, body.rank() + "안은 Spring 재검증을 통과하지 못해 고를 수 없음");
        }
        long eid = repo.addDecision(id, body.rank(), body.action(), body.actor(), body.reason() == null ? "" : body.reason());
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("decision_id", eid, "run_id", id));
    }

    @GetMapping("/runs/{id}/decisions")
    List<Map<String, Object>> decisions(@PathVariable long id) {
        return repo.decisions(id);
    }

    private Map<String, Object> view(RunRepository.RunRow r) {
        Map<String, Object> v = new LinkedHashMap<>();
        v.put("id", r.id());
        v.put("case_id", r.caseId());
        v.put("case_key", r.caseKey());
        v.put("case_title", r.caseTitle());
        v.put("payload_hash", r.payloadHash());
        v.put("arrivals", r.arrivals());
        v.put("status", r.status());
        v.put("top", r.top());
        v.put("time_limit_s", r.timeLimit());
        v.put("engine", r.engine());
        v.put("profile", r.profile());
        v.put("worker", r.worker());
        v.put("error", r.error());
        v.put("created_at", r.createdAt());
        v.put("started_at", r.startedAt());
        v.put("finished_at", r.finishedAt());
        v.put("summary", r.summary() == null ? null : json.readValue(r.summary(), Map.class));
        return v;
    }
}
