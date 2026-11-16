#!/usr/bin/env bash
# 지우지 않고 멈추거나(stop) 다시 켠다(start). 컨테이너·DB 볼륨·이미지는 그대로 남는다.
# 맥을 다시 켰을 때는 Docker Desktop만 열면 컨테이너가 저절로 뜬다(restart: unless-stopped) — make stop으로 멈춘 것만 make start가 필요하다.
source "$(dirname "$0")/lib.sh"
need docker curl python3
docker_up
[ -f "$SECRETS_FILE" ] || die "runtime/secrets.env가 없습니다 → make up"
[ -n "$(dc ps -aq)" ] || die "컨테이너가 없습니다 → make up"
case "${1:-}" in
  stop)
    active=$(curl -s -m 5 "$BASE_URL/api/system/status" 2>/dev/null |
      python3 -c 'import json,sys; print(json.load(sys.stdin)["db"]["counts"]["active"])' 2>/dev/null || echo "?")
    running=$(dc ps -q dmin-server)
    if [ -n "$running" ] && [ "$active" != "0" ] && [ "${FORCE:-}" != "1" ]; then
      die "대기·실행 중인 계산 ${active}건('?'는 상태를 못 읽음) → 끝난 뒤 다시, 또는 FORCE=1 make stop (실행 중이던 것은 다시 켠 뒤 맥박이 90초 끊겨 FAILED, 대기 중이던 것은 이어서 돈다)"
    fi
    say "컨테이너 멈추기 (지우지 않음 — DB·이미지 그대로)"
    dc stop
    dc ps -a --format 'table {{.Name}}\t{{.Status}}'
    info "다시 켜기: make start"
    ;;
  start)
    say "컨테이너 켜기"
    s0=$(date +%s)
    dc up -d --wait --no-deps dmin-postgres >/dev/null
    dc up -d --wait --no-deps "${APPS[@]}" >/dev/null
    say "앱 기다리기 (입구 → Spring → DB·Python)"
    wait_until 300 healthy || die "300초 안에 /api/system/status가 정상이 아닙니다 → make status · make logs"
    dc ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'
    info "다시 켜는 데 $(( $(date +%s) - s0 ))초 · 화면: $BASE_URL · 확인: make status"
    ;;
  *)
    die "쓰는 법: $0 stop|start"
    ;;
esac
