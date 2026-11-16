package com.dmin.runs;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.support.TransactionTemplate;

/** run·run_step·decision_event 테이블. SQL을 그대로 쓴다(SKIP LOCKED·advisory lock·JSONB). */
@Repository
class RunRepository {

    /** Spring 인스턴스가 몇 개든 계산은 한 번에 1건 (정의서 4.1 "동시 계산 1건"). 이 번호로 점유 순간만 직렬화한다. */
    static final long CLAIM_LOCK = 0x444D494EL; // "DMIN"

    /** 실행 접수 잠금 = 이 값 + 데이터 id. 같은 데이터의 접수만 줄을 세운다("RUN" + 0). CLAIM_LOCK과 겹치지 않는다. */
    static final long CREATE_LOCK_BASE = 0x52554E0000000000L;

    private final JdbcClient jdbc;
    private final TransactionTemplate tx;

    RunRepository(JdbcClient jdbc, TransactionTemplate tx) {
        this.jdbc = jdbc;
        this.tx = tx;
    }

    /** 접수 결과. duplicate면 같은 데이터·같은 설정(후보 수·제한 시간·엔진·해석)으로 이미 대기·실행 중인 실행의 id다. */
    record Created(long id, boolean duplicate) {}

    /**
     * 같은 데이터·같은 설정으로 대기·실행 중인 실행이 없을 때만 새로 만든다.
     * 확인과 넣기 사이에 다른 요청(다른 인스턴스)이 끼어들지 못하게 데이터마다 advisory xact lock을 잡는다.
     */
    Created createIfNotActive(long caseId, int top, int timeLimit, String engine, String profile) {
        return tx.execute(status -> {
            jdbc.sql("SELECT pg_advisory_xact_lock(:k)").param("k", CREATE_LOCK_BASE + caseId).query((rs, i) -> 1).list();
            Optional<Long> active = activeFor(caseId, top, timeLimit, engine, profile);
            if (active.isPresent()) {
                return new Created(active.get(), true);
            }
            return new Created(create(caseId, top, timeLimit, engine, profile), false);
        });
    }

    private long create(long caseId, int top, int timeLimit, String engine, String profile) {
        return jdbc.sql("""
                        INSERT INTO run (case_id, status, top_n, time_limit_s, engine, profile)
                        VALUES (:c, 'QUEUED', :t, :l, :e, :p) RETURNING id""")
                .param("c", caseId)
                .param("t", top)
                .param("l", timeLimit)
                .param("e", engine)
                .param("p", profile)
                .query(Long.class)
                .single();
    }

    private Optional<Long> activeFor(long caseId, int top, int timeLimit, String engine, String profile) {
        return jdbc.sql("""
                        SELECT id FROM run WHERE case_id = :c AND top_n = :t AND time_limit_s = :l AND engine = :e AND profile = :p
                          AND status IN ('QUEUED', 'RUNNING') ORDER BY id LIMIT 1""")
                .param("c", caseId)
                .param("t", top)
                .param("l", timeLimit)
                .param("e", engine)
                .param("p", profile)
                .query(Long.class)
                .optional();
    }

    /**
     * 대기 중인 실행 하나를 이 인스턴스가 가져간다. 다른 실행이 RUNNING이면 가져가지 않는다.
     * advisory xact lock으로 '확인 + 점유'를 한 덩어리로 만들고, SKIP LOCKED로 두 인스턴스가 같은 행을 집지 않게 한다.
     */
    Optional<Long> claimNext(String worker) {
        return tx.execute(status -> {
            jdbc.sql("SELECT pg_advisory_xact_lock(:k)").param("k", CLAIM_LOCK).query((rs, i) -> 1).list();
            return jdbc.sql("""
                            UPDATE run SET status = 'RUNNING', started_at = now(), heartbeat_at = now(), worker = :w
                            WHERE id = (
                                SELECT id FROM run r
                                WHERE r.status = 'QUEUED'
                                  AND NOT EXISTS (SELECT 1 FROM run x WHERE x.status = 'RUNNING')
                                ORDER BY r.created_at, r.id
                                FOR UPDATE SKIP LOCKED
                                LIMIT 1)
                            RETURNING id""")
                    .param("w", worker)
                    .query(Long.class)
                    .optional();
        });
    }

    void heartbeat(long runId) {
        jdbc.sql("UPDATE run SET heartbeat_at = now() WHERE id = :id AND status = 'RUNNING'")
                .param("id", runId)
                .update();
    }

    /** 맥박이 끊긴 RUNNING(그 인스턴스가 죽었거나 재시작) → FAILED, 열려 있던 단계도 닫는다. 다른 인스턴스가 이 일을 한다. */
    int failStale(Duration after) {
        List<Long> failed = tx.execute(status -> {
            List<Long> ids = jdbc.sql("""
                            UPDATE run SET status = 'FAILED', finished_at = now(),
                                   error = '실행하던 서버(' || coalesce(worker, '?') || ')의 맥박이 끊겨 중단됨 — 다시 실행하세요'
                            WHERE status = 'RUNNING' AND heartbeat_at < now() - make_interval(secs => :s)
                            RETURNING id""")
                    .param("s", (double) after.toSeconds())
                    .query(Long.class)
                    .list();
            for (long id : ids) {
                closeOpenSteps(id, "맥박 끊김");
            }
            return ids;
        });
        return failed == null ? 0 : failed.size();
    }

    /** 이 인스턴스가 아직 그 실행의 주인(RUNNING · worker 같음)일 때만 단계를 연다. 열었으면 true. */
    boolean stepStart(long runId, String worker, int seq, String name) {
        return jdbc.sql("""
                        INSERT INTO run_step (run_id, seq, name, status)
                        SELECT :r, :s, :n, 'RUNNING'
                        WHERE EXISTS (SELECT 1 FROM run WHERE id = :r AND status = 'RUNNING' AND worker = :w)""")
                        .param("r", runId)
                        .param("s", seq)
                        .param("n", name)
                        .param("w", worker)
                        .update()
                == 1;
    }

    /** 열려 있는(RUNNING) 단계만 닫는다. 이미 닫힌 단계(맥박 끊김으로 FAILED 등)는 덮어쓰지 않는다. */
    void stepEnd(long runId, int seq, boolean ok, String detail) {
        jdbc.sql("""
                        UPDATE run_step SET status = :st, finished_at = now(), detail = :d
                        WHERE run_id = :r AND seq = :s AND status = 'RUNNING'""")
                .param("st", ok ? "OK" : "FAILED")
                .param("d", detail)
                .param("r", runId)
                .param("s", seq)
                .update();
    }

    /** 실행이 도중에 끝났을 때 아직 RUNNING인 단계를 FAILED로 닫는다. 있던 설명 뒤에 이유를 붙인다. */
    void closeOpenSteps(long runId, String detail) {
        jdbc.sql("""
                        UPDATE run_step SET status = 'FAILED', finished_at = now(), detail = coalesce(detail || ' · ', '') || :d
                        WHERE run_id = :r AND status = 'RUNNING'""")
                .param("d", detail)
                .param("r", runId)
                .update();
    }

    /**
     * 이 인스턴스(worker)가 잡고 있는 RUNNING 실행만 끝낸다. 바뀐 행 수를 돌려준다.
     * 0이면 이미 다른 인스턴스가 끝낸 실행(맥박 끊김 → FAILED 등)이라 덮어쓰지 않은 것이다.
     */
    int finish(long runId, String worker, String status, String error, String summary, String verification, String result) {
        return jdbc.sql("""
                        UPDATE run SET status = :st, finished_at = now(), error = :e,
                               summary = CAST(:sm AS jsonb), verification = CAST(:v AS jsonb), result = CAST(:r AS jsonb)
                        WHERE id = :id AND status = 'RUNNING' AND worker = :w""")
                .param("st", status)
                .param("e", error)
                .param("sm", summary)
                .param("v", verification)
                .param("r", result)
                .param("id", runId)
                .param("w", worker)
                .update();
    }

    record RunRow(
            long id,
            long caseId,
            String caseKey,
            String caseTitle,
            String payloadHash,
            int arrivals,
            String status,
            int top,
            int timeLimit,
            String engine,
            String profile,
            String worker,
            String error,
            OffsetDateTime createdAt,
            OffsetDateTime startedAt,
            OffsetDateTime finishedAt,
            String summary) {}

    private static final String RUN_SELECT = """
            SELECT r.id, r.case_id, c.case_key, c.title, c.payload_hash, c.arrivals, r.status, r.top_n, r.time_limit_s, r.engine, r.profile, r.worker,
                   r.error, r.created_at, r.started_at, r.finished_at, r.summary::text AS summary
            FROM run r JOIN plan_case c ON c.id = r.case_id""";

    private static RunRow row(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new RunRow(
                rs.getLong("id"),
                rs.getLong("case_id"),
                rs.getString("case_key"),
                rs.getString("title"),
                rs.getString("payload_hash"),
                rs.getInt("arrivals"),
                rs.getString("status"),
                rs.getInt("top_n"),
                rs.getInt("time_limit_s"),
                rs.getString("engine"),
                rs.getString("profile"),
                rs.getString("worker"),
                rs.getString("error"),
                rs.getObject("created_at", OffsetDateTime.class),
                rs.getObject("started_at", OffsetDateTime.class),
                rs.getObject("finished_at", OffsetDateTime.class),
                rs.getString("summary"));
    }

    Optional<RunRow> find(long id) {
        return jdbc.sql(RUN_SELECT + " WHERE r.id = :id").param("id", id).query((rs, i) -> row(rs)).optional();
    }

    List<RunRow> list(int limit) {
        return jdbc.sql(RUN_SELECT + " ORDER BY r.id DESC LIMIT :l").param("l", limit).query((rs, i) -> row(rs)).list();
    }

    long caseOf(long runId) {
        return jdbc.sql("SELECT case_id FROM run WHERE id = :id").param("id", runId).query(Long.class).single();
    }

    String json(long runId, String column) {
        if (!List.of("result", "verification", "summary").contains(column)) {
            throw new IllegalArgumentException(column);
        }
        return jdbc.sql("SELECT " + column + "::text FROM run WHERE id = :id")
                .param("id", runId)
                .query(String.class)
                .optional()
                .orElse(null);
    }

    List<Map<String, Object>> steps(long runId) {
        return jdbc.sql("""
                        SELECT seq, name, status, started_at, finished_at, detail,
                               round(extract(epoch FROM (coalesce(finished_at, now()) - started_at))::numeric, 2) AS seconds
                        FROM run_step WHERE run_id = :r ORDER BY seq""")
                .param("r", runId)
                .query()
                .listOfRows();
    }

    long addDecision(long runId, int rank, String action, String actor, String reason) {
        return jdbc.sql("""
                        INSERT INTO decision_event (run_id, candidate_rank, action, actor, reason)
                        VALUES (:r, :k, :a, :who, :why) RETURNING id""")
                .param("r", runId)
                .param("k", rank)
                .param("a", action)
                .param("who", actor)
                .param("why", reason)
                .query(Long.class)
                .single();
    }

    List<Map<String, Object>> decisions(long runId) {
        return jdbc.sql("""
                        SELECT id, candidate_rank, action, actor, reason, created_at
                        FROM decision_event WHERE run_id = :r ORDER BY id""")
                .param("r", runId)
                .query()
                .listOfRows();
    }

    Map<String, Object> counts() {
        return jdbc.sql("""
                        SELECT (SELECT count(*) FROM plan_case) AS cases,
                               (SELECT count(*) FROM run) AS runs,
                               (SELECT count(*) FROM run WHERE status IN ('QUEUED', 'RUNNING')) AS active,
                               (SELECT count(*) FROM eta_snapshot) AS eta_snapshots""")
                .query()
                .singleRow();
    }
}
