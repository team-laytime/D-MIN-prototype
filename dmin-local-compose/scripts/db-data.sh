#!/usr/bin/env bash
# DB 데이터 백업·가져오기 (데이터만 — 표 정의는 Flyway 마이그레이션이 만든다).
#   backup              runtime/backup-data-<날짜시각>.sql 로 뜬다
#   import <파일>       빈 DB에 넣는다 (데이터가 이미 있으면 거절). 한 트랜잭션이라 실패하면 아무것도 안 들어간다
#   import-k8s          쿠버네티스 판(dmin-local-k8s)에서 떠 온 runtime/import/k8s-data-*.sql 중 가장 최근 것을 넣는다
source "$(dirname "$0")/lib.sh"
need docker
docker_up
PG=dmin-postgres
[ "$(docker inspect -f '{{.State.Running}}' "$PG" 2>/dev/null)" = "true" ] || die "DB 컨테이너가 떠 있지 않습니다 → make up"
q() { docker exec "$PG" psql -U dmin_owner -d dmin -tAc "$1"; }
counts() { q "SELECT 'plan_case=' || (SELECT count(*) FROM plan_case) || ' · run=' || (SELECT count(*) FROM run) || ' · decision_event=' || (SELECT count(*) FROM decision_event) || ' · eta_snapshot=' || (SELECT count(*) FROM eta_snapshot)"; }

case "${1:-}" in
  backup)
    out="$ROOT/runtime/backup-data-$(date +%Y-%m-%d-%H%M).sql"
    ( umask 077; docker exec "$PG" pg_dump -U dmin_owner -d dmin --data-only --exclude-table=flyway_schema_history > "$out.tmp" && mv "$out.tmp" "$out" )
    info "백업: ${out#$ROOT/} ($(grep -c '^COPY ' "$out")개 표 · $(wc -c < "$out" | tr -d ' ')바이트) — 지금 줄 수: $(counts)"
    info "runtime/ 안이라 make clean이면 같이 지워집니다 — 남길 백업은 밖으로 옮기세요"
    ;;
  import|import-k8s)
    if [ "$1" = "import-k8s" ]; then
      f=$(ls -t "$ROOT"/runtime/import/k8s-data-*.sql 2>/dev/null | head -1 || true)
      [ -n "$f" ] || die "runtime/import/k8s-data-*.sql 이 없습니다"
    else
      f="${2:-}"; [ -f "$f" ] || die "파일이 없습니다: ${f:-(경로를 주세요)}"
    fi
    n=$(q "SELECT (SELECT count(*) FROM plan_case) + (SELECT count(*) FROM run) + (SELECT count(*) FROM decision_event) + (SELECT count(*) FROM eta_snapshot)")
    [ "$n" = "0" ] || die "DB에 이미 데이터가 있습니다($(counts)) — 빈 DB에만 넣습니다. 처음부터 다시 하려면 make clean CONFIRM=yes → make up"
    say "가져오기: ${f#$ROOT/}"
    # 파일을 컨테이너에 복사하지 않고 표준 입력으로 넘긴다(백업 파일은 권한 600이라 컨테이너 안 postgres 사용자가 못 읽는다)
    if docker exec -i "$PG" psql -U dmin_owner -d dmin -1 -q -v ON_ERROR_STOP=1 -f - < "$f" >/dev/null; then
      info "넣은 뒤 줄 수: $(counts)"
    else
      die "가져오기 실패 — 아무것도 들어가지 않았습니다(한 트랜잭션)"
    fi
    ;;
  *)
    die "쓰는 법: $0 backup | import <파일> | import-k8s"
    ;;
esac
