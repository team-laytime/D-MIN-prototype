#!/usr/bin/env bash
# 팀원 코드(berth_sim, CP-SAT 최적화)를 agent에 그대로 복사한다. 한 글자도 고치지 않는다 — 고칠 것은 원본에서 고친 뒤 다시 복사한다.
#   원본  → TEAM_SRC (기본 ~/Downloads/berth_sim_share — 팀원이 공유한 폴더)
#   복사본 → agent/src/dmin_agent/berth_sim/  (+ VENDORED.md: 언제·어디서·파일별 sha256)
# 우리 쪽에서 쓰는 곳은 agent/src/dmin_agent/team_engine.py(어댑터) 하나뿐이다. 엑셀·화면·보고서 파일은 복사는 하지만 부르지 않는다.
source "$(dirname "$0")/lib.sh"
TEAM_SRC="${TEAM_SRC:-$HOME/Downloads/berth_sim_share}"
[ -f "$TEAM_SRC/berth_sim/cpsat_model.py" ] || die "팀원 코드가 없습니다: $TEAM_SRC/berth_sim (TEAM_SRC=경로로 지정)"
DST="$ROOT/agent/src/dmin_agent/berth_sim"
rm -rf "$DST"
mkdir -p "$DST/after_etb"
cp "$TEAM_SRC"/berth_sim/*.py "$DST/"
cp "$TEAM_SRC"/berth_sim/after_etb/*.py "$DST/after_etb/"
{
  echo "# 팀원 코드 복사본 (berth_sim)"
  echo
  echo "- 복사한 날: $(date '+%Y-%m-%d %H:%M') · 원본: \`${TEAM_SRC/#$HOME/~}/berth_sim\` · 복사: \`scripts/sync-team-engine.sh\`"
  echo "- **이 폴더의 .py는 고치지 않는다.** 원본에서 고친 뒤 다시 복사한다. 우리 요청 → 이 코드로 바꾸는 일은 \`../team_engine.py\`가 한다."
  echo "- 원본 README의 실행 방법(start.command · serve_cpsat.py)은 여기서 쓰지 않는다. 엑셀(openpyxl)을 읽는 sample_loader·master_data.load_master도 부르지 않는다."
  echo
  echo "| 파일 | sha256 앞 16자 | 줄 |"
  echo "|---|---|---|"
  (cd "$DST" && for f in *.py after_etb/*.py; do
     printf '| %s | %s | %s |\n' "$f" "$(shasum -a 256 "$f" | cut -c1-16)" "$(wc -l < "$f" | tr -d ' ')"
   done)
} > "$DST/VENDORED.md"
n=$(ls "$DST"/*.py "$DST"/after_etb/*.py | wc -l | tr -d ' ')
info "팀원 코드 $n개 파일 → agent/src/dmin_agent/berth_sim/ (목록: VENDORED.md)"
info "다음: make test → make up"
