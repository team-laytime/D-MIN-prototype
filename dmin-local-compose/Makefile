# D-MIN 로컬 실행판 (Docker Compose) — 자주 쓰는 명령 (설명: README.md)
# 쿠버네티스는 쓰지 않는다. 값은 .env(공공데이터 키·포트)와 runtime/secrets.env(DB·Grafana 비밀번호, 자동 생성)에서 온다.
SHELL := /bin/bash
export ENV_FILE ?= $(CURDIR)/.env
DC := docker compose --project-directory $(CURDIR) --env-file $(ENV_FILE) --env-file $(CURDIR)/runtime/secrets.env

.PHONY: help up secrets restart verify verify-full data status logs test render sync-engine sync-team stop start down clean collect psql backup import-k8s-data

help:            ## 명령 목록
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  make %-16s %s\n", $$1, $$2}'

up:              ## 처음부터 끝까지: 비밀값 → 이미지 → DB → 마이그레이션 → 앱 (처음 약 5분 · 코드를 안 고쳤으면 SKIP_BUILD=1 make up)
	./scripts/up.sh

secrets:         ## 비밀값만 준비 (.env · runtime/secrets.env)
	./scripts/secrets.sh

restart:         ## Spring만 다시 띄우기 (.env의 키를 바꾼 뒤) — 다시 뜨는 동안 /api가 잠깐 끊긴다
	$(DC) up -d --wait --no-deps --force-recreate dmin-server

verify:          ## 확인 순서 0~10단계 (약 2분)
	python3 scripts/verify.py

verify-full:     ## + 11단계 실제 크기 (샘플 54건 + 팀원 가상 데이터 54척 두 엔진, 약 5분 더)
	FULL=1 python3 scripts/verify.py

data:            ## data/inbox/의 *.json·*.csv를 넣고 후보 계산까지 (FILE=경로 로 한 파일만 · ENGINE=ppt-milp PROFILE=ppt 로 기존 엔진)
	@if [ -n "$(FILE)" ]; then python3 scripts/dmin-data.py run "$(FILE)"; else python3 scripts/dmin-data.py inbox; fi

status:          ## 컨테이너·입구 한눈에
	@./scripts/status.sh

logs:            ## Spring·Python 최근 로그
	-$(DC) logs --tail=40 dmin-server
	-$(DC) logs --tail=20 dmin-agent

test:            ## 컨테이너 없이 단위 테스트 (Spring 정답 대조 · Python 엔진)
	cd server && ./gradlew --no-daemon -q test
	cd agent && uv run --frozen pytest -q

render:          ## compose.yaml만 확인 (값 파일이 있어야 한다 — 없으면 make secrets)
	$(DC) config -q && echo "compose.yaml ok"

sync-engine:     ## docs/milp/ppt의 엔진·규칙 표를 다시 복사 (원본을 고쳤을 때)
	./scripts/sync-engine.sh

sync-team:       ## 팀원 코드(berth_sim)를 agent에 그대로 복사 (TEAM_SRC=팀원 폴더, 기본 ~/Downloads/berth_sim_share)
	./scripts/sync-team-engine.sh

collect:         ## 공공데이터 수집을 지금 한 번 (매일 06:00에 저절로 도는 것과 같은 일)
	docker exec dmin-collector sh /collector.sh once

stop:            ## 지우지 않고 멈추기 (DB·이미지 그대로, 계산 중이면 거절)
	./scripts/stop-start.sh stop

start:           ## 멈춘 컨테이너 다시 켜기 → 입구·DB·Python 정상까지 기다림
	./scripts/stop-start.sh start

psql:            ## DB에 들어가기 (앱 계정 dmin_app)
	docker exec -it dmin-postgres psql -U dmin_app -d dmin

backup:          ## DB 데이터 백업 → runtime/backup-data-<시각>.sql
	./scripts/db-data.sh backup

import-k8s-data: ## 쿠버네티스 판에서 떠 온 데이터(runtime/import/)를 빈 DB에 넣기
	./scripts/db-data.sh import-k8s

down:            ## 컨테이너·네트워크 지우기 (DB 볼륨은 남는다 — 다시 make up 하면 데이터 그대로)
	$(DC) down

clean:           ## 전부 지우기: 컨테이너 + DB·지표 볼륨 + runtime/(비밀번호·백업·검증 기록) — CONFIRM=yes 가 있어야 한다
	@[ "$(CONFIRM)" = "yes" ] || { echo "DB 데이터와 runtime/(백업 포함)이 지워집니다. 남길 백업을 밖으로 옮긴 뒤: make clean CONFIRM=yes"; exit 1; }
	-$(DC) down -v
	rm -rf runtime
