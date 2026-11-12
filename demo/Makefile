# 척화비 데모 — 자주 쓰는 명령 (설명은 README.md)
PY ?= .venv/bin/python
export PYTHONPATH := src

setup:   ## 가상환경 + 의존성 (uv)
	test -d .venv || uv venv --python 3.12 .venv
	uv pip install --python $(PY) -e ".[dev,llm,aws]"

test:    ## 단위·통합 테스트
	$(PY) -m pytest tests

verify:  ## 정답 세트·검증 시나리오·최적성 (하나라도 틀리면 실패)
	$(PY) -m demurrage verify --strict

run:     ## 통합 데모 시나리오 실행 → out/
	$(PY) -m demurrage run S05-storm-rush --out out --db sqlite:///runtime/demurrage.db

serve:   ## API + 화면 (http://127.0.0.1:8000)
	DATABASE_URL=sqlite:///runtime/demurrage.db $(PY) -m demurrage serve

bench:   ## 성능·확장성 (8·12·16척)
	$(PY) -m demurrage bench --sizes 8 12 16 --repeat 5

up:      ## 컨테이너(앱 + Postgres)
	docker compose up -d --build --wait

smoke:   ## 배포 직후 정답 검문
	$(PY) scripts/smoke.py http://localhost:8000

down:
	docker compose down

ci: test verify   ## CI와 같은 순서(로컬)

batch-local:    ## AWS 없이 정기 보고서 배치 실행·저장 확인
	$(PY) -m demurrage.jobs.daily_report --output-dir runtime/reports

infra-check:    ## AWS 접속 없이 YAML·Terraform 설정과 모의 plan 검사
	kubectl kustomize deploy/k8s/base > /dev/null
	terraform -chdir=deploy/terraform fmt -check -recursive
	terraform -chdir=deploy/terraform init -backend=false -input=false
	terraform -chdir=deploy/terraform validate
	terraform -chdir=deploy/terraform test

.PHONY: setup test verify run serve bench up smoke down ci batch-local infra-check
