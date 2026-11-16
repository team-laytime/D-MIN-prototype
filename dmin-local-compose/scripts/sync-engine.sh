#!/usr/bin/env bash
# docs/milp/ppt(원본)의 수리계획법 엔진과 규칙 표를 다시 복사한다. 식은 원본에서만 고친다.
#   엔진 → agent/src/dmin_agent/engine/ (import만 패키지 상대 경로로 바꿈)
#   규칙 표 → rules/terminal.json · server/src/main/resources/rules/ · agent/src/dmin_agent/engine/rules/ (세 곳이 같아야 재검증이 통과)
#   정답(응답 JSON) → server/src/test/resources/golden/ (Spring 계산 모듈 교차 검사용 · verify.py 기대 금액)
#   예시 데이터(요청 JSON) → data/samples/ (verify.py가 넣는 것) · front/public/samples/ (화면 '예시' 버튼)
# 규칙 표나 cases/를 바꿨으면 정답부터 원본에서 다시 만든 뒤 돌린다: (docs/milp/ppt에서) python3 run.py cases/… --out out
source "$(dirname "$0")/lib.sh"
SRC="${SRC:-$ROOT/../docs/milp/ppt}"
[ -f "$SRC/run.py" ] || die "원본이 없습니다: $SRC (SRC=경로로 지정)"
ENG="$ROOT/agent/src/dmin_agent/engine"
for f in pptcalc.py planner.py solver.py run.py; do
  sed -E -e 's/^from (pptcalc|planner|solver) import/from .\1 import/' -e '/^sys\.path\.insert\(0, str\(HERE\)\)$/d' "$SRC/$f" > "$ENG/$f"
done
cp "$SRC/rules/terminal.json" "$ROOT/rules/terminal.json"
cp "$SRC/rules/terminal.json" "$ROOT/server/src/main/resources/rules/terminal.json"
cp "$SRC/rules/terminal.json" "$ENG/rules/terminal.json"
G="$ROOT/server/src/test/resources/golden"
cp "$SRC/cases/example-request.json" "$G/EXAMPLE-3.request.json"
cp "$SRC/cases/sample-week.json" "$G/SAMPLE-W46.request.json"
cp "$SRC/cases/sample-week-weather.json" "$G/SAMPLE-W46-WX.request.json"
for n in EXAMPLE-3 SAMPLE-W46 SAMPLE-W46-WX; do cp "$SRC/out/$n.response.json" "$G/$n.response.json"; done
for d in "$ROOT/data/samples" "$ROOT/front/public/samples"; do
  cp "$SRC/cases/example-request.json" "$d/example-3.json"
  cp "$SRC/cases/sample-week.json" "$d/sample-week-54.json"
done
shasum -a 256 "$ROOT/rules/terminal.json" "$ROOT/server/src/main/resources/rules/terminal.json" "$ENG/rules/terminal.json" | awk '{print "  " substr($1,1,16) "  " $2}'
info "예시 데이터: data/samples/ · front/public/samples/ (example-3.json · sample-week-54.json)"
info "주의: 규칙 표나 cases/를 바꿨다면 정답부터 다시 → cd $SRC && python3 run.py cases/… --out out → 다시 make sync-engine"
info "다음: make test → make up"
