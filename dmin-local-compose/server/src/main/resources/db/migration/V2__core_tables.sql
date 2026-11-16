-- 데이터 입구 → 실행 → 재검증 → 사람의 결정. 정의서 5.3 '저장 데이터'의 최소판이다.

-- 들어온 데이터 한 벌 (= 최적화 요청 JSON 한 개). 같은 내용이 다시 오면 같은 행을 쓴다(지문 payload_hash).
CREATE TABLE plan_case (
    id            BIGSERIAL PRIMARY KEY,
    case_key      TEXT        NOT NULL,
    title         TEXT        NOT NULL DEFAULT '',
    source        TEXT        NOT NULL CHECK (source IN ('json', 'csv')),
    file_name     TEXT,
    payload_hash  TEXT        NOT NULL,
    payload       JSONB       NOT NULL,
    arrivals      INT         NOT NULL,
    plan_start    TEXT        NOT NULL,
    plan_end      TEXT        NOT NULL,
    warnings      JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX plan_case_payload_hash ON plan_case (payload_hash);

-- 실행 한 번. 상태: QUEUED → RUNNING → SUCCEEDED / PARTIAL / FAILED (정의서 4.1)
CREATE TABLE run (
    id            BIGSERIAL PRIMARY KEY,
    case_id       BIGINT      NOT NULL REFERENCES plan_case (id),
    status        TEXT        NOT NULL CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED')),
    top_n         INT         NOT NULL DEFAULT 3,
    time_limit_s  INT         NOT NULL DEFAULT 120,
    worker        TEXT,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at    TIMESTAMPTZ,
    heartbeat_at  TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    summary       JSONB,
    verification  JSONB,
    result        JSONB
);
CREATE INDEX run_status_created ON run (status, created_at);
CREATE INDEX run_case ON run (case_id);

-- 실행의 단계: INPUT(입력 검사) → SOLVE(Python 솔버) → VERIFY(Spring 재검증) → PUBLISH(공개)
CREATE TABLE run_step (
    run_id       BIGINT      NOT NULL REFERENCES run (id),
    seq          INT         NOT NULL,
    name         TEXT        NOT NULL,
    status       TEXT        NOT NULL CHECK (status IN ('RUNNING', 'OK', 'FAILED')),
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    detail       TEXT,
    PRIMARY KEY (run_id, seq)
);

-- 사람의 선택·취소. 추가 전용: 앱 계정에는 UPDATE·DELETE 권한을 주지 않는다(V3, 정의서 5.3).
CREATE TABLE decision_event (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT      NOT NULL REFERENCES run (id),
    candidate_rank  INT         NOT NULL,
    action          TEXT        NOT NULL CHECK (action IN ('SELECT', 'CANCEL')),
    actor           TEXT        NOT NULL,
    reason          TEXT        NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX decision_event_run ON decision_event (run_id, created_at);

-- 입항 신고 ETA를 매일 쌓는다. 신고가 바뀌면 새 줄이 생기고, 같으면 버린다 → 최초 ETA와 실제 입항의 차이를 나중에 잴 수 있다
-- (demo/docs/16: '지난 30일 입항 1,000건 중 995건이 최종 신고만 남음 — 직접 쌓아야 함').
CREATE TABLE eta_snapshot (
    id            BIGSERIAL PRIMARY KEY,
    collected_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    call_sign     TEXT        NOT NULL,
    entry_year    TEXT        NOT NULL,
    entry_count   TEXT        NOT NULL,
    vessel_name   TEXT,
    filing        TEXT        NOT NULL,
    eta           TEXT        NOT NULL,
    facility      TEXT,
    grt           DOUBLE PRECISION,
    raw           JSONB       NOT NULL
);
CREATE UNIQUE INDEX eta_snapshot_dedup ON eta_snapshot (call_sign, entry_year, entry_count, filing, eta);
