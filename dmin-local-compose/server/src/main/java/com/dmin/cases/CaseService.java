package com.dmin.cases;

import com.dmin.common.error.DminException;
import com.dmin.common.error.ErrorCode;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.dmin.laytime.CaseParser;
import com.dmin.laytime.Rules;
import com.dmin.laytime.Times;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

/**
 * 데이터 입구 (정의서 5.1-1, FR-01~04). 들어온 데이터를 검사하고, 통과한 것만 지문과 함께 저장한다.
 * 검사는 Spring 계산 모듈(CaseParser)이 한다 — 솔버가 받는 것과 같은 해석이다.
 */
@Service
public class CaseService {

    public record CaseView(
            long id,
            @JsonProperty("case_key") String caseKey,
            String title,
            String source,
            @JsonProperty("file_name") String fileName,
            @JsonProperty("payload_hash") String payloadHash,
            int arrivals,
            @JsonProperty("plan_start") String planStart,
            @JsonProperty("plan_end") String planEnd,
            List<String> warnings,
            @JsonProperty("created_at") OffsetDateTime createdAt,
            boolean duplicate) {}

    private final JdbcClient jdbc;
    private final ObjectMapper json;

    CaseService(JdbcClient jdbc, ObjectMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    public CaseView importJson(String body, String fileName) {
        JsonNode doc;
        try {
            doc = json.readTree(body);
        } catch (RuntimeException e) {
            throw new DminException(ErrorCode.VALIDATION, "JSON으로 읽을 수 없음: " + firstLine(e.getMessage()));
        }
        return store(doc, "json", fileName);
    }

    public CaseView importCsv(String text, String fileName, String title, String planStart, String planEnd) {
        String base = fileName == null ? "upload" : fileName.replaceAll("\\.[^.]*$", "");
        CaseCsv.Converted c = CaseCsv.convert(json, text, "CSV-" + base, title == null ? base : title, planStart, planEnd);
        if (c.doc() == null) { // 머리글부터 틀려 표를 읽을 수 없을 때
            throw new DminException(ErrorCode.VALIDATION, "CSV 검사 실패 " + c.errors().size() + "건", c.errors());
        }
        return store(c.doc(), "csv", fileName, c.errors()); // 칸 오류와 입력 검사 오류를 한 번에 알려 준다
    }

    CaseView store(JsonNode doc, String source, String fileName) {
        return store(doc, source, fileName, List.of());
    }

    @SuppressWarnings("unchecked")
    CaseView store(JsonNode doc, String source, String fileName, List<String> earlier) {
        if (doc != null && hasNul(doc)) { // PostgreSQL JSONB는 NUL(U+0000)을 저장하지 못한다 → DB 오류(500) 전에 입력 오류로 돌려준다
            throw new DminException(ErrorCode.VALIDATION, "글자 NUL(\\u0000)은 받지 않음");
        }
        Rules rules;
        try {
            JsonNode patch = doc.get("rule_patch");
            rules = patch == null || patch.isNull() ? Rules.bundled() : Rules.bundled(json.treeToValue(patch, Map.class));
        } catch (RuntimeException e) {
            throw new DminException(ErrorCode.VALIDATION, "rule_patch를 적용할 수 없음: " + firstLine(e.getMessage()));
        }
        CaseParser.Parsed parsed = CaseParser.parse(doc, rules);
        List<String> errors = new java.util.ArrayList<>(earlier);
        errors.addAll(parsed.errors());
        if (!errors.isEmpty()) {
            throw new DminException(ErrorCode.VALIDATION, "입력 검사 실패 " + errors.size() + "건", errors);
        }
        String hash = CanonicalJson.hash(json, doc);
        Optional<Long> existing = jdbc.sql("SELECT id FROM plan_case WHERE payload_hash = :h")
                .param("h", hash)
                .query(Long.class)
                .optional();
        if (existing.isPresent()) {
            return get(existing.get(), true);
        }
        String key = doc.path("id").isString() ? doc.get("id").asString() : parsed.data().id();
        Optional<Long> inserted = jdbc.sql("""
                        INSERT INTO plan_case (case_key, title, source, file_name, payload_hash, payload, arrivals, plan_start, plan_end, warnings)
                        VALUES (:key, :title, :source, :file, :hash, CAST(:payload AS jsonb), :n, :ps, :pe, CAST(:warnings AS jsonb))
                        ON CONFLICT (payload_hash) DO NOTHING
                        RETURNING id""")
                .param("key", key)
                .param("title", parsed.data().title())
                .param("source", source)
                .param("file", fileName)
                .param("hash", hash)
                .param("payload", json.writeValueAsString(doc))
                .param("n", parsed.data().arrivals().size())
                .param("ps", Times.iso(parsed.data().start()))
                .param("pe", Times.iso(parsed.data().end()))
                .param("warnings", json.writeValueAsString(parsed.warnings()))
                .query(Long.class)
                .optional();
        if (inserted.isEmpty()) { // 같은 내용이 동시에 들어와 다른 요청이 먼저 넣었다 → 그 행이 '이미 있는 데이터'다
            long id = jdbc.sql("SELECT id FROM plan_case WHERE payload_hash = :h")
                    .param("h", hash)
                    .query(Long.class)
                    .single();
            return get(id, true);
        }
        return get(inserted.get(), false);
    }

    public List<CaseView> list(int limit) {
        return jdbc.sql("""
                        SELECT id, case_key, title, source, file_name, payload_hash, arrivals, plan_start, plan_end,
                               warnings::text AS warnings, created_at
                        FROM plan_case ORDER BY id DESC LIMIT :limit""")
                .param("limit", limit)
                .query((rs, i) -> view(rs, false))
                .list();
    }

    public CaseView get(long id, boolean duplicate) {
        return jdbc.sql("""
                        SELECT id, case_key, title, source, file_name, payload_hash, arrivals, plan_start, plan_end,
                               warnings::text AS warnings, created_at
                        FROM plan_case WHERE id = :id""")
                .param("id", id)
                .query((rs, i) -> view(rs, duplicate))
                .optional()
                .orElseThrow(() -> new DminException(ErrorCode.NOT_FOUND, "데이터 " + id + " 없음"));
    }

    public String payload(long id) {
        return jdbc.sql("SELECT payload::text FROM plan_case WHERE id = :id")
                .param("id", id)
                .query(String.class)
                .optional()
                .orElseThrow(() -> new DminException(ErrorCode.NOT_FOUND, "데이터 " + id + " 없음"));
    }

    @SuppressWarnings("unchecked")
    private CaseView view(java.sql.ResultSet rs, boolean duplicate) throws java.sql.SQLException {
        return new CaseView(
                rs.getLong("id"),
                rs.getString("case_key"),
                rs.getString("title"),
                rs.getString("source"),
                rs.getString("file_name"),
                rs.getString("payload_hash"),
                rs.getInt("arrivals"),
                rs.getString("plan_start"),
                rs.getString("plan_end"),
                json.readValue(rs.getString("warnings"), List.class),
                rs.getObject("created_at", OffsetDateTime.class),
                duplicate);
    }

    /** 문자열·키 어디에든 NUL(U+0000)이 있는가. */
    static boolean hasNul(JsonNode n) {
        if (n.isString()) {
            return n.asString().indexOf('\0') >= 0;
        }
        for (String k : n.propertyNames()) {
            if (k.indexOf('\0') >= 0 || hasNul(n.get(k))) {
                return true;
            }
        }
        if (n.isArray()) {
            for (JsonNode v : n.values()) {
                if (hasNul(v)) {
                    return true;
                }
            }
        }
        return false;
    }

    private static String firstLine(String s) {
        if (s == null) {
            return "";
        }
        int i = s.indexOf('\n');
        return i < 0 ? s : s.substring(0, i);
    }
}
