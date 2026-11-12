# 척화비 데모 — 울산 CLX 체선료 플래너 (SEAGATE 체선 관리 개선 컨셉)

> 가상 데이터 · 의사결정 보조용 · 최종 접안 계획은 담당자가 확정합니다.

선박·부두·기상 조건과 **계약서**를 바탕으로 **예상 체선료를 근거와 함께 계산**하고, **제약을 지키는 접안 순서 후보 3개**를 기준안(도착 순서)과 비교해 **남은 리스크·보고서·메일 초안**까지 만든 뒤, **사람이 고른 안을 기록**합니다. 계산서의 금액마다 계약 조항·운영 기준이 근거로 붙습니다. 팀 요구사항서(최종 탭), 피그마 워크플로우 7단계, 현업 멘토링 PPT(06~11쪽) 계산식을 따릅니다.

- 설계·결정·검증 문서: [`docs/00-final-report.md`](docs/00-final-report.md) (색인 [`docs/README.md`](docs/README.md))
- 결과(2026-11-09): 대표 데모 S05 기준안 $112,919 → 1안 $87,489(−22.5%), 최적 증명 0.3초 · 시나리오 16개 모두 후보 위반 0건 · 정답 세트 272칸 100% · 테스트 88개
- 들어 있는 것: 화면 11개, 가상 계약서 23건, 시나리오 16개(+ 검증 4개), 아키텍처 다이어그램 2장
- EKS 연결 준비: [`deploy/README.md`](deploy/README.md) — YAML·CronJob·Terraform·다음 주 연결 순서. [설정 이유와 팀의 역할](docs/14-eks-architecture.md)

## 빠른 시작

### 1) 로컬 (uv, Python 3.12)

```bash
make setup
```

```bash
make verify
```

```bash
make serve
```

브라우저: http://127.0.0.1:8000 — 열자마자 대표 데모를 계산해 '접안 계획 비교'가 뜹니다. 선박 막대를 누르면 계산서, 계산서의 계약 칩을 누르면 계약서 조항으로 갑니다.

### 2) 컨테이너 (앱 + PostgreSQL)

```bash
cp .env.example .env
```

```bash
docker compose up -d --build --wait
```

```bash
python3 scripts/smoke.py http://localhost:8000
```

### 3) 명령줄만

```bash
PYTHONPATH=src .venv/bin/python -m demurrage run S05-storm-rush --out out
```

```bash
PYTHONPATH=src .venv/bin/python -m demurrage bench --sizes 8 12 16
```

## 명령

| 명령 | 하는 일 |
|---|---|
| `make test` | 단위·통합·배치·배포 설정 테스트 |
| `make verify` | 정답 세트·검증 시나리오·완전 탐색 비교·시나리오 16개 — 하나라도 틀리면 실패(CI 문지기) |
| `make run` | 대표 데모 실행 → `out/<run_id>/`(보고서·메일·타임라인·CSV·run.json) |
| `make serve` | API + 화면, API 문서는 `/docs` |
| `make bench` | 8·12·16척 성능·최적성 갭 |
| `make up` · `make smoke` · `make down` | 컨테이너 기동 · 배포 직후 정답 검문 · 중지 |
| `make batch-local` | AWS 없이 정기 보고서 계산·검증·로컬 저장 |
| `make infra-check` | Kubernetes 렌더링·Terraform 설정·AWS mock 검사 |
| `python scripts/make_diagrams.py` | 아키텍처 다이어그램 2장을 다시 그림(docs/assets, 화면) |

## 설정 (환경변수)

| 이름 | 기본 | 뜻 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./runtime/demurrage.db` | Compose에서는 PostgreSQL |
| `LLM_PROVIDER` | `none` | `anthropic`이면 보고서 문장에만 LLM 사용(숫자는 엔진 값) |
| `ANTHROPIC_API_KEY` | (없음) | LLM 키 — 저장소에 넣지 않음 |
| `LLM_MODEL` | `claude-opus-5-5` | |
| `LLM_BASE_URL` | `https://api.anthropic.com` | |
| `LLM_COST_CAP_USD` | `1.0` | 실행 1회 LLM 비용 상한 |
| `DEMURRAGE_DATA_DIR` | `./data` | 규칙 표·계약서·시나리오·정답 세트 위치 |

## 폴더

```
src/demurrage/   domain · rules · data · engine (계산, 표준 라이브러리만 / rules/contracts.py가 계약서를 읽음)
                 agents · report · llm (처리 단계·보고서·LLM 경계)
                 store · api · web · cli.py · verify.py (저장·API·화면·명령)
data/            contracts(가상 계약서 23건) · scenarios(16개 + validation 4개)
                 master(부두 기준 정보) · rules(계약 규칙·규칙 ID·리스크 문구) · golden(손계산 정답 15묶음)
                 history(가상 실적) · public(공공데이터 저장본)
tests/           단위·통합·배치·배포 설정 테스트
scripts/         smoke.py(배포 직후 검문) · make_diagrams.py
deploy/          EKS YAML · Terraform · DB 연결 예시 · 자원 연결 가이드
docs/            설계·결정·검증 문서, assets/에 다이어그램·보고서 예
```
