#!/usr/bin/env bash
# 컨테이너 상태와 입구(/api/system/status)를 한눈에 보여 준다.
source "$(dirname "$0")/lib.sh"
need docker curl python3
docker_up
[ -f "$SECRETS_FILE" ] || die "runtime/secrets.env가 없습니다 → make up"
if [ -z "$(dc ps -aq)" ]; then
  die "컨테이너가 없습니다 → make up"
fi
dc ps -a --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'
echo
curl -s -m 5 "$BASE_URL/api/system/status" | python3 -c '
import json, sys
t = sys.stdin.read().strip()
print(json.dumps(json.loads(t), indent=4, ensure_ascii=False) if t.startswith("{") else "입구 응답: " + (t[:60] or "없음") + " — 막 켰다면 Spring이 뜰 때까지 30초쯤 뒤 다시 (계속되면 make logs)")'
echo
echo "  화면: $BASE_URL  ·  Grafana: $GRAFANA_URL"
