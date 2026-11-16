-- 실행마다 어떤 엔진·어떤 규칙 해석으로 풀었나 (2026-11-16, 팀원 코드 berth_sim 연결).
--   engine  ppt-milp   기존 엔진 (docs/milp/ppt, HiGHS)
--           team-cpsat 팀 엔진 (팀원 코드 berth_sim, OR-Tools CP-SAT) — 규칙 해석 team으로만 돈다
--   profile rules/terminal.json의 profiles 이름. 데이터의 rule_patch 위에 덮어쓴다(ppt = 표 그대로)
-- 예전 실행은 모두 기존 엔진 · 기존 해석이었으므로 기본값이 그대로 맞다. 권한은 V3의 표 단위 GRANT가 새 열에도 걸린다.
ALTER TABLE run ADD COLUMN engine  TEXT NOT NULL DEFAULT 'ppt-milp' CHECK (engine IN ('ppt-milp', 'team-cpsat'));
ALTER TABLE run ADD COLUMN profile TEXT NOT NULL DEFAULT 'ppt';
