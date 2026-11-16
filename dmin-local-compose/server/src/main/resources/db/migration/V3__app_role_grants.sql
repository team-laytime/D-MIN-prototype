-- 앱 계정(${app_user})의 권한. 테이블 주인은 마이그레이션 계정이고, 이 파일은 마이그레이션 Job만 돌린다(EKS 계획 3-2 #5).
-- 앱 계정 자체는 DB를 처음 만들 때 만든다: 로컬은 Postgres 초기화 스크립트, RDS는 DBA 절차.
GRANT USAGE ON SCHEMA public TO ${app_user};
GRANT SELECT, INSERT ON plan_case TO ${app_user};
GRANT SELECT, INSERT, UPDATE ON run, run_step TO ${app_user};
GRANT SELECT, INSERT ON decision_event TO ${app_user};      -- 추가 전용
GRANT SELECT, INSERT ON eta_snapshot TO ${app_user};
GRANT SELECT ON flyway_schema_history TO ${app_user};       -- 상태 화면에서 스키마 버전을 보여 준다
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ${app_user};
