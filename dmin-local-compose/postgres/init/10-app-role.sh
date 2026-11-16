#!/bin/sh
# DB를 처음 만들 때 한 번: 앱 계정(dmin_app)을 만든다. 표 권한은 마이그레이션(V3)이 준다.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v app_pw="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE dmin_app LOGIN PASSWORD :'app_pw';
GRANT CONNECT ON DATABASE dmin TO dmin_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
