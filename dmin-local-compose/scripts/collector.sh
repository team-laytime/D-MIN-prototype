#!/bin/sh
# 수집 타이머 (dmin-collector 컨테이너 안에서 돈다 · 쿠버네티스 판의 CronJob dmin-collect-eta 자리).
#   loop  매일 COLLECT_AT_KST(기본 06:00, 한국 시간)에 Spring의 내부 수집 경로를 부른다
#   once  지금 한 번 부른다 (make collect)
# 한 번에 90초 한도, 실패하면 20초 쉬고 최대 3번. 계산·저장은 Spring이 한다 — 이 컨테이너는 '깨우기'만 해서 DB·키를 갖지 않는다.
set -u
URL="${COLLECT_URL:-http://dmin-server:8080/internal/collect/eta}"
AT="${COLLECT_AT_KST:-06:00}"
trap 'exit 0' TERM INT

nap() { sleep "$1" & wait $!; }   # 기다리는 중에도 멈춤 신호(docker stop)를 바로 받는다

collect() {
  n=1
  while [ "$n" -le 3 ]; do
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] 수집 시도 $n/3 → $URL"
    if out=$(curl -fsS --max-time 90 -X POST "$URL" 2>&1); then
      echo "$out"
      return 0
    fi
    echo "$out"
    n=$((n + 1))
    [ "$n" -le 3 ] && nap 20
  done
  echo "수집 실패 (3번 모두)"
  return 1
}

case "${1:-loop}" in
  once)
    collect
    ;;
  loop)
    h=${AT%%:*}; m=${AT##*:}
    target=$(( ${h#0} * 3600 + ${m#0} * 60 ))
    echo "수집 타이머 시작: 매일 ${AT} KST"
    while :; do
      now=$(date -u +%s)
      sod=$(( (now + 32400) % 86400 ))            # 한국 시간으로 오늘 0시부터 지난 초 (UTC+9, 서머타임 없음)
      wait_s=$(( (target - sod + 86400) % 86400 ))
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] 다음 수집까지 ${wait_s}초"
      nap "$wait_s"
      collect || true
      nap 61                                       # 같은 분에 두 번 돌지 않게
    done
    ;;
  *)
    echo "쓰는 법: collector.sh loop|once" >&2
    exit 2
    ;;
esac
