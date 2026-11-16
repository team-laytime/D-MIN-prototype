#!/usr/bin/env bash
# 비밀값 준비. 값은 화면·로그에 찍지 않는다 (쿠버네티스 판에서는 같은 값을 Secret 3개로 만들었다).
#   .env                  공공데이터포털 키 — Spring 컨테이너에만 들어간다. 없으면 .env.example을 복사한다(있는 파일은 건드리지 않는다)
#   runtime/secrets.env   OWNER_PASSWORD(마이그레이션 계정 dmin_owner) · APP_PASSWORD(앱 계정 dmin_app) · GRAFANA_PASSWORD(admin) — 처음에 만든다
source "$(dirname "$0")/lib.sh"
need openssl docker
if [ ! -f "$ENV_FILE" ]; then
  ( umask 077; cp "$ROOT/.env.example" "$ENV_FILE" )
  info ".env가 없어 .env.example을 복사했습니다 (공공데이터 키를 넣으면 실시간 기능이 켜집니다)"
fi
chmod 600 "$ENV_FILE"
if [ ! -f "$SECRETS_FILE" ]; then
  # DB 볼륨이 이미 있는데 비밀번호를 새로 만들면 DB 안의 계정과 어긋난다 → 멈추고 알린다
  if docker volume inspect dmin_pgdata >/dev/null 2>&1; then
    die "DB 볼륨(dmin_pgdata)은 있는데 runtime/secrets.env가 없습니다 → 예전 secrets.env를 되돌려 놓거나, DB를 버려도 되면 make clean CONFIRM=yes 뒤 다시 make up"
  fi
  ( umask 077; printf 'OWNER_PASSWORD=%s\nAPP_PASSWORD=%s\nGRAFANA_PASSWORD=%s\n' "$(openssl rand -hex 24)" "$(openssl rand -hex 24)" "$(openssl rand -hex 12)" > "$SECRETS_FILE" )
  info "DB·Grafana 비밀번호를 새로 만들었습니다 (runtime/secrets.env, 커밋 안 됨)"
fi
chmod 600 "$SECRETS_FILE"
# shellcheck disable=SC1090
( source "$SECRETS_FILE"
  [ -n "${OWNER_PASSWORD:-}" ] && [ -n "${APP_PASSWORD:-}" ] && [ -n "${GRAFANA_PASSWORD:-}" ] ) ||
  die "runtime/secrets.env에 빈 값이 있습니다 (OWNER_PASSWORD · APP_PASSWORD · GRAFANA_PASSWORD)"
key="$(env_get PUBLIC_DATA_SERVICE_KEY)"
if [ -n "$key" ]; then info "공공데이터 키: 있음 (${#key}자, .env)"; else info "공공데이터 키: 없음 → 실시간 기능만 꺼짐 (.env)"; fi
unset key
# 두 파일이 git에 올라가지 않는지 (저장소 안일 때만)
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  for f in "$ENV_FILE" "$SECRETS_FILE"; do
    git -C "$ROOT" check-ignore -q "$f" || die "$(basename "$f")가 .gitignore에 걸리지 않습니다 — 커밋되면 안 되는 파일입니다"
  done
fi
