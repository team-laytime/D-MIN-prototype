#!/usr/bin/env bash
# 공통 설정. 값은 두 파일에서 온다(둘 다 커밋 안 됨): .env(공공데이터 키·포트) · runtime/secrets.env(DB·Grafana 비밀번호, 자동 생성).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
SECRETS_FILE="$ROOT/runtime/secrets.env"
mkdir -p "$ROOT/runtime"

# .env에서 한 줄 읽기 (CR·앞뒤 공백·따옴표를 벗긴다). 없으면 빈 값.
env_get() {
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^["'\'']//' -e 's/["'\'']$//' || true
}
_port="${DMIN_PORT:-$(env_get DMIN_PORT)}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${_port:-18089}}"
_gport="${GRAFANA_PORT:-$(env_get GRAFANA_PORT)}"
GRAFANA_URL="http://127.0.0.1:${_gport:-13000}"
unset _port _gport

# 오래 떠 있는 서비스(마이그레이션은 한 번 돌고 끝나므로 여기 없다)
APPS=(dmin-agent dmin-server dmin-front caddy dmin-collector prometheus grafana)

# docker compose를 항상 같은 값 파일로 부른다
dc() { docker compose --project-directory "$ROOT" --env-file "$ENV_FILE" --env-file "$SECRETS_FILE" "$@"; }
say() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
need() { for c in "$@"; do command -v "$c" >/dev/null 2>&1 || die "'$c' 명령이 없습니다 (README '준비물' 참고)"; done; }
docker_up() { docker info >/dev/null 2>&1 || die "Docker Desktop이 켜져 있지 않습니다"; }

# 입구 → Spring → DB·에이전트까지 답하면 0
healthy() {
  curl -s -m 5 "$BASE_URL/api/system/status" 2>/dev/null |
    python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d["db"]["ok"] and d["agent"]["ok"] else 1)' 2>/dev/null
}
wait_until() {   # wait_until 초 명령 — 명령이 성공할 때까지, 마감 시각 기준
  local end=$(( $(date +%s) + $1 )); shift
  until "$@"; do [ "$(date +%s)" -lt "$end" ] || return 1; sleep 2; done
}
