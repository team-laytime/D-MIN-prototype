package com.dmin.system;

import com.dmin.laytime.Rules;
import com.dmin.publicdata.PublicDataProperties;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.info.BuildProperties;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.ObjectMapper;

/**
 * 한 번에 보는 시스템 상태: 서버·DB(스키마 버전)·Python 에이전트·규칙 표·공공데이터 키 유무·건수.
 * 검증 스크립트(scripts/verify.py)와 화면 맨 위 상태 줄이 이것을 쓴다. 비밀 값은 넣지 않는다.
 */
@RestController
class SystemController {

    private final JdbcClient jdbc;
    private final StatusProbe probe;
    private final PublicDataProperties publicData;
    private final ObjectMapper json;
    private final ObjectProvider<BuildProperties> build;

    SystemController(
            JdbcClient jdbc, StatusProbe probe, PublicDataProperties publicData, ObjectMapper json, ObjectProvider<BuildProperties> build) {
        this.jdbc = jdbc;
        this.probe = probe;
        this.publicData = publicData;
        this.json = json;
        this.build = build;
    }

    @GetMapping("/system/status")
    Map<String, Object> status() {
        Rules rules = Rules.bundled();
        Map<String, Object> out = new LinkedHashMap<>();
        Map<String, Object> server = new LinkedHashMap<>();
        server.put("pod", probe.workerId());
        server.put("version", build.getIfAvailable() == null ? "dev" : build.getIfAvailable().getVersion());
        server.put("rules_version", rules.version());
        server.put("rules_sha256", rules.sha256());
        out.put("server", server);

        Map<String, Object> db = new LinkedHashMap<>();
        try {
            db.put("ok", true);
            // 마지막으로 성공한 마이그레이션. version은 글자라 max()로 고르면 '10'이 '9'보다 작게 나온다
            db.put("schema_version", jdbc.sql("""
                            SELECT version FROM flyway_schema_history WHERE success ORDER BY installed_rank DESC LIMIT 1""")
                    .query(String.class)
                    .optional()
                    .orElse(null));
            db.put("counts", probe.counts());
        } catch (RuntimeException e) {
            db.put("ok", false);
            db.put("error", e.getClass().getSimpleName());
        }
        out.put("db", db);

        Map<String, Object> agent = new LinkedHashMap<>();
        agent.put("url", probe.agentUrl());
        try {
            Map<?, ?> h = json.readValue(probe.agentHealth(), Map.class);
            agent.put("ok", "ok".equals(h.get("status")));
            agent.put("engine", h.get("engine"));
            agent.put("engines", h.get("engines")); // 팀 엔진(팀원 코드 berth_sim)·기존 엔진 버전
            agent.put("rules_version", h.get("rules_version"));
            agent.put("rules_sha256", h.get("rules_sha256"));
            agent.put("rules_same", rules.sha256().equals(h.get("rules_sha256")));
            agent.put("busy", h.get("busy"));
        } catch (RuntimeException e) {
            agent.put("ok", false);
            agent.put("error", e.getMessage());
        }
        out.put("agent", agent);

        Map<String, Object> pd = new LinkedHashMap<>();
        pd.put("configured", publicData.configured());
        out.put("public_data", pd);
        return out;
    }
}
