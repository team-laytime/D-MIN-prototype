package com.dmin.internal;

import com.dmin.publicdata.EntryService;
import com.dmin.publicdata.PublicDataException;
import java.util.LinkedHashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.transaction.TransactionException;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.ObjectMapper;

/**
 * 컨테이너 네트워크 안에서만 부르는 경로(/internal/**, /api 아래가 아니라 Caddy가 넘기지 않는다).
 * 수집 타이머 컨테이너(dmin-collector)가 매일 06:00 KST에 부른다: 울산 입항 신고 ETA를 eta_snapshot에 쌓는다.
 * 부를 때마다 입항 건(호출부호·연도·입항횟수)마다 그때 가장 나중 신고 하나만 넣는다(그 사이에 지나간 단계는 남지 않는다).
 * 같은 (입항 건·신고 단계·ETA)는 한 번만 남으므로, 새 줄이 생기는 때 = 처음 보는 입항 건 · 신고 단계가 바뀜 · ETA가 바뀜.
 * 한 번 부른 것은 한 트랜잭션으로 넣는다. DB에 못 넣으면 500 {ok:false}이고 아무 줄도 남지 않는다.
 */
@RestController
class CollectController {

    private static final Logger log = LoggerFactory.getLogger(CollectController.class);

    private final EntryService entry;
    private final JdbcClient jdbc;
    private final ObjectMapper json;
    private final TransactionTemplate tx;

    CollectController(EntryService entry, JdbcClient jdbc, ObjectMapper json, TransactionTemplate tx) {
        this.entry = entry;
        this.jdbc = jdbc;
        this.json = json;
        this.tx = tx;
    }

    private record Saved(int seen, int inserted) {}

    @PostMapping("/internal/collect/eta")
    ResponseEntity<Map<String, Object>> collectEta() {
        Map<String, Object> out = new LinkedHashMap<>();
        EntryService.Snapshot snap;
        try {
            snap = entry.snapshot(true);
        } catch (PublicDataException e) {
            out.put("ok", false);
            out.put("error", e.getMessage());
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(out);
        }
        Saved saved;
        long total;
        try {
            saved = tx.execute(status -> {
                int inserted = 0;
                int seen = 0;
                for (Map<String, Object> r : EntryService.pickLatest(snap.rows())) {
                    if (r.get("callSign") == null || r.get("year") == null || r.get("count") == null || r.get("filing") == null) {
                        continue;
                    }
                    seen++;
                    inserted += jdbc.sql("""
                                    INSERT INTO eta_snapshot (call_sign, entry_year, entry_count, vessel_name, filing, eta, facility, grt, raw)
                                    VALUES (:cs, :y, :n, :name, :f, :eta, :fac, :grt, CAST(:raw AS jsonb))
                                    ON CONFLICT DO NOTHING""")
                            .param("cs", r.get("callSign"))
                            .param("y", r.get("year"))
                            .param("n", r.get("count"))
                            .param("name", r.get("name"))
                            .param("f", r.get("filing"))
                            .param("eta", r.get("eta"))
                            .param("fac", r.get("facility"))
                            .param("grt", r.get("grt"))
                            .param("raw", json.writeValueAsString(r))
                            .update();
                }
                return new Saved(seen, inserted);
            });
            total = jdbc.sql("SELECT count(*) FROM eta_snapshot").query(Long.class).single();
        } catch (DataAccessException | TransactionException e) {
            log.error("ETA 수집: DB 저장 실패", e);
            String why = e.getMostSpecificCause().getMessage(); // 첫 줄만 (예: ERROR: permission denied for table eta_snapshot)
            why = why == null || why.isBlank() ? e.getClass().getSimpleName() : why.lines().findFirst().orElse(why);
            out.put("ok", false);
            out.put("error", "DB 저장 실패: " + why);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(out);
        }
        out.put("ok", true);
        out.put("fetched_at", snap.fetchedAt());
        out.put("window", snap.window());
        out.put("arrivals_seen", saved.seen());
        out.put("inserted", saved.inserted());
        out.put("total_snapshots", total);
        return ResponseEntity.ok(out);
    }
}
