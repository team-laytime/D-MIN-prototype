#!/usr/bin/env bash
# 순서대로 띄운다: 비밀값 → 이미지 → DB → 마이그레이션(성공해야 다음) → 앱 → 상태.
# 마이그레이션이 실패하면 앱을 바꾸기 전에 멈춘다 → 떠 있던 앱은 옛 버전 그대로 돈다(쿠버네티스 판 deploy.sh와 같은 약속).
source "$(dirname "$0")/lib.sh"
need docker openssl curl python3
docker_up
t0=$(date +%s)

say "1/6 비밀값"
"$ROOT/scripts/secrets.sh"

say "2/6 이미지 3개 빌드 (Spring·Python은 빌드 안에서 정답 테스트 — 하나라도 틀리면 이미지가 안 만들어진다)"
if [ "${SKIP_BUILD:-}" = "1" ]; then
  info "SKIP_BUILD=1 → 빌드 건너뜀 (있는 이미지 사용)"
else
  dc build dmin-server dmin-agent dmin-front
fi
: > "$ROOT/runtime/images.env.tmp"
for app in server agent front; do
  id=$(docker image inspect "dmin-compose-$app:local" --format '{{.Id}}' 2>/dev/null | sed 's/^sha256://' | cut -c1-12) || true
  [ -n "$id" ] || die "이미지 dmin-compose-$app:local 이 없습니다 (SKIP_BUILD 없이 다시)"
  info "dmin-compose-$app:local  (이미지 $id)"
  echo "$(echo "$app" | tr a-z A-Z)_IMAGE=$id" >> "$ROOT/runtime/images.env.tmp"
done
mv "$ROOT/runtime/images.env.tmp" "$ROOT/runtime/images.env"

say "3/6 DB 준비 (Postgres + pgvector, 볼륨 dmin_pgdata)"
dc up -d --wait dmin-postgres

say "4/6 DB 마이그레이션 (Flyway, 마이그레이션 계정) — 끝나야 앱을 바꾼다"
log="$ROOT/runtime/migrate.log"
dc rm -sf dmin-migrate >/dev/null 2>&1 || true          # 지난번 것은 지우고 새로 돌린다 (끝난 컨테이너는 '마이그레이션 끝남' 기록으로 남는다)
dc up -d --no-deps dmin-migrate >/dev/null 2>&1 || die "마이그레이션 컨테이너를 띄우지 못했습니다 → docker logs dmin-migrate"
code=$(docker wait dmin-migrate)
docker logs dmin-migrate > "$log" 2>&1 || true
if [ "$code" != "0" ]; then
  tail -40 "$log" | sed 's/^/  /'
  die "마이그레이션 실패(종료 코드 $code) — 앱은 바꾸지 않았습니다(떠 있던 앱은 그대로 돕니다). 전체 로그: runtime/migrate.log"
fi
grep -E 'Successfully (applied|validated)|Schema .* is up to date|Current version' "$log" | sed 's/^.*INFO [0-9]* --- \[[^]]*\] //' | sed 's/^/  /' || true

say "5/6 앱 올리기 (Python · Spring · Vue · 입구 Caddy · 수집 타이머 · Prometheus · Grafana) — 모두 정상(healthy)이 될 때까지 기다림"
dc up -d --wait --no-deps "${APPS[@]}"

say "6/6 상태"
dc ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'
wait_until 60 healthy || die "입구에서 /api/system/status가 정상이 아닙니다 → make status · make logs"
info "띄우는 데 $(( $(date +%s) - t0 ))초"
info "화면: $BASE_URL  ·  Grafana: $GRAFANA_URL (admin / runtime/secrets.env의 GRAFANA_PASSWORD)  ·  검증: make verify"
