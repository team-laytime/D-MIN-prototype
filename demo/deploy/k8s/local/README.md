# AWS 없이 kind로 배포 실습

Docker로 앱 이미지를 빌드하고 kind로 로컬 Kubernetes 노드를 실행한다. `kubectl apply -k`가 기존 `base` YAML에 로컬 설정을 합쳐 적용한다. API는 실습용 PostgreSQL에 접속하고, CronJob의 배치 명령은 `--output-dir /reports`로 보고서를 볼륨에 저장한다. API Pod에 같은 볼륨을 읽기 전용으로 연결해 완료된 Job의 파일을 꺼낼 수 있다.

## 실습 클러스터 준비

명령은 저장소 루트에서 실행한다. Docker Desktop, kind, kubectl, Python 3가 필요하다. 아래 빌드는 Apple Silicon의 kind 노드를 기준으로 한다. Intel/AMD 노드에서는 `linux/amd64`를 사용한다. 클러스터를 이미 만든 상태라면 새로 생성하는 명령은 건너뛴다.

```bash
rehearsal_dir="$PWD/demo/runtime/k8s-rehearsal"
mkdir -p "$rehearsal_dir"
kind create cluster --name demurrage-rehearsal --kubeconfig "$rehearsal_dir/kubeconfig" --wait 120s
docker buildx build --platform linux/arm64 --provenance=false --sbom=false --load --tag demurrage-app:local-rehearsal demo
kind load docker-image --name demurrage-rehearsal demurrage-app:local-rehearsal
```

```bash
k() { kubectl --kubeconfig "$PWD/demo/runtime/k8s-rehearsal/kubeconfig" --context kind-demurrage-rehearsal "$@"; }
k apply -f demo/deploy/k8s/namespace.yaml
if ! k -n demurrage get secret demurrage-secrets >/dev/null 2>&1; then
  rehearsal_password=$(openssl rand -hex 16)
  k -n demurrage create secret generic demurrage-secrets \
    --from-literal="POSTGRES_PASSWORD=$rehearsal_password" \
    --from-literal="DATABASE_URL=postgresql+psycopg://demurrage:$rehearsal_password@demurrage-postgres:5432/demurrage?sslmode=disable"
  unset rehearsal_password
fi
k -n demurrage apply -f demo/deploy/k8s/local/postgres.yaml
k -n demurrage rollout status deployment/demurrage-postgres --timeout=120s
k apply -k demo/deploy/k8s/local
k -n demurrage rollout status deployment/demurrage-api --timeout=120s
```

로컬 DB 데이터는 DB Pod의 `emptyDir`에 있으며 Pod를 교체하면 초기화된다. 보고서는 별도 PVC에 저장되어 Job Pod가 종료된 뒤에도 확인할 수 있다.

## API와 보고서 확인

새 터미널에서 저장소 루트로 이동한 뒤 포트를 연다. 다른 터미널에서 smoke를 실행하면 API 상태, DB 연결, 계산 결과를 확인할 수 있다.

```bash
kubectl --kubeconfig "$PWD/demo/runtime/k8s-rehearsal/kubeconfig" --context kind-demurrage-rehearsal \
  -n demurrage port-forward --address 127.0.0.1 service/demurrage-api 18080:80
```

```bash
python3 demo/scripts/smoke.py http://127.0.0.1:18080
```

`k` 함수를 정의한 터미널에서 CronJob 템플릿으로 한 번 실행할 Job을 만든다. `suspend: true` 상태에서도 이 명령을 실행할 수 있다.

```bash
job_name="demurrage-report-$(date +%s)"
k -n demurrage create job "$job_name" --from=cronjob/demurrage-daily-report
k -n demurrage wait --for=condition=complete "job/$job_name" --timeout=120s
k -n demurrage logs "job/$job_name"
report_path=$(k -n demurrage logs "job/$job_name" | python3 -c 'import json, sys; print(json.load(sys.stdin)["location"])')
k -n demurrage exec deployment/demurrage-api -- cat "$report_path" > demo/runtime/k8s-rehearsal/report.json
```

같은 입력과 버전으로 같은 날짜에 다시 실행하면 배치 로그에 `already_exists`가 기록될 수 있다. 이 경우 기존 보고서를 읽는다.

화면에서 실행한 샘플과 배치 보고서를 함께 대조하려면 [샘플 시연과 발표 결론](../../../docs/15-k8s-sample-demo.md)의 명령을 사용한다.

실습이 끝나면 포트 포워딩을 `Ctrl+C`로 종료하고, 필요할 때 아래 명령으로 실습 클러스터와 그 안의 데이터를 정리한다. 꺼내 둔 `report.json`은 작업 폴더에서 읽을 수 있다.

```bash
kind delete cluster --name demurrage-rehearsal --kubeconfig "$PWD/demo/runtime/k8s-rehearsal/kubeconfig"
```
