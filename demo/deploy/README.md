# EKS 연결 준비와 배포 순서

작성: 2026-11-11. 현재 실행 가능한 **Python 데모 이미지**를 기준으로 한다. 설정 이유와 팀의 역할은 [아키텍처 설명](../docs/14-eks-architecture.md)에 있다. Spring Boot·LangGraph 분리 방향은 그 문서의 확장 항목에 구분했다.

사전 검사 결과: [검증 기록](VALIDATION.md).

이 폴더를 준비하는 작업은 AWS 접속·자원 생성·배포를 실행하지 않는다. 기존 EKS·S3·ECR을 사용하는 것이 기본이며, Terraform으로 새 자원을 만드는 범위는 변수로 선택한다.

## 1. 들어 있는 것

| 경로 | 용도 |
|---|---|
| `k8s/base/` | API Deployment·내부 Service·서비스 계정 2개·CronJob·설정 ConfigMap |
| `k8s/namespace.yaml` | 기본 `demurrage` namespace를 직접 만들 권한이 있을 때 쓰는 선택 파일 |
| `terraform/` | 기존 EKS 조회, 선택적 S3·ECR·IAM 역할·Pod Identity 연결, S3 state 설정 |
| `database.env.example` | PostgreSQL 연결 Secret을 만드는 입력 예시 |
| `../scripts/render_eks.py` | 받은 이미지·버킷·리전·namespace를 검증해 하나의 YAML로 생성 |
| `../src/demurrage/jobs/daily_report.py` | 실제 계산 엔진 → 실행 검증 → 보고서 JSON 저장 |

기본 CronJob은 **매일 한국 시간 09:00, `suspend: true`**다. 수동 실행과 S3 저장을 확인한 뒤 활성화한다. 기본 입력은 이미지의 가상 시나리오 `S05-storm-rush`다. 공공데이터 수집·최신 업무 입력 연동·승인·메일 발송은 이 배치에 포함하지 않는다.

## 2. 자원 없이 지금 확인하기

실제 로컬 Kubernetes에 API를 띄우고 CronJob의 수동 Job과 보고서 저장까지 확인하려면 [kind 배포 실습](k8s/local/README.md)을 따라간다.

명령은 `demo/`에서 실행한다. Python 3.12+, Docker, kubectl(Kustomize 포함), Terraform 1.10+가 필요하다. CI의 Terraform 검증 버전은 1.14.0이다. AWS provider는 `.terraform.lock.hcl`에 기록한다. 실제 접속용 kubectl은 제공받은 EKS 버전과 호환되는 버전을 설치한다.

```bash
make setup
make test
make verify
make batch-local
make infra-check
```

`make batch-local`은 `runtime/reports/reports/<한국 날짜>/<시나리오>/<내용 식별자>.json`을 만든다. 같은 입력·날짜·배포 버전·계산 결과면 기존 파일을 보존한다. 로컬 배치에는 AWS 라이브러리나 접속 정보가 필요하지 않다. `make setup`은 S3 테스트를 위해 `aws` extra도 설치한다.

`make infra-check`의 `init -backend=false`는 provider를 다운로드하므로 인터넷이 필요하다. `validate`와 mock 기반 `terraform test`는 AWS 자원을 조회·생성하지 않는다. 실제 IAM 권한·네트워크·클러스터 정책·노드 자원은 다음 주 연결 시 검증한다.

현재 작업 폴더 루트의 `.github/workflows/demo-ci.yml`에도 앱·컨테이너·인프라 검사를 연결했다. 이 폴더를 GitHub 저장소 루트로 올리면 실행할 수 있다. 원격 CI 실행과 클라우드 자동 배포는 아직 수행하지 않았다.

## 3. 다음 주에 받아 둘 값과 권한

| 항목 | 받아 둘 내용 |
|---|---|
| 사용자 접근 | AWS 계정 ID·리전·IAM 사용자/SSO 역할·CLI 인증 방법 |
| EKS | 클러스터 이름·버전·접속 경로(VPN 등)·팀 namespace·CPU/메모리 quota |
| 배포 권한 | 해당 namespace의 Deployment·Service·ConfigMap·Secret·ServiceAccount·Job·CronJob 조회/생성/수정, Pod·로그 조회, port-forward |
| 이미지 | 같은 계정·리전의 ECR repository URL, 내 이미지 push 권한, 노드의 이미지 pull 권한, CPU 아키텍처 |
| 보고서 | 같은 계정·리전의 S3 버킷·사용 prefix, 소유 계정, 암호화/KMS 키 정보 |
| 프로그램 권한 | `demurrage-batch` 서비스 계정에 연결할 Pod Identity 역할·정책, 연결을 누가 관리하는지 |
| PostgreSQL | DB 이름·endpoint·계정·비밀번호·CA, EKS에서 5432로 접근 가능한 네트워크/보안 그룹 |
| Terraform | 팀이 관리할 자원 범위, 별도 state 버킷·key·접근 권한·담당자 |

사용자의 EKS 접근에는 EKS Access Entry/접근 정책 또는 RBAC 설정이 필요하다. AWS 콘솔에 로그인할 수 있다는 사실만으로 namespace 배포 권한이 생기지는 않는다.

이 구성의 Pod Identity는 지원되는 Linux EC2 노드 또는 EKS Auto Mode를 전제로 한다. 일반 EKS에서는 Pod Identity Agent와 노드 역할의 `eks-auth:AssumeRoleForPodIdentity` 권한을 제공자에게 확인한다. Auto Mode에는 관련 기능이 포함된다. Fargate·Windows 노드 등 지원 범위가 다르면 IRSA 등 제공 환경에 맞는 인증 방식으로 변경해야 한다. Agent 설치나 클러스터 add-on 변경은 이 구성에서 수행하지 않는다.

## 4. AWS 인증과 대상 확인

제공자의 안내대로 CLI 프로필을 설정한다. SSO라면 로그인 후 확인한다. 아래 환경변수의 자리표시자는 실제 값으로 바꾼다. 비밀번호나 access key는 여기에 넣지 않는다.

```bash
export AWS_PROFILE=your-provided-profile
export AWS_REGION=ap-northeast-2
export AWS_ACCOUNT_ID=123456789012
export EKS_CLUSTER=your-provided-cluster
export K8S_NAMESPACE=demurrage
export KUBE_CONTEXT=demurrage-dev
export ECR_REPOSITORY=demurrage
export REPORTS_BUCKET=your-provided-reports-bucket
export REPORTS_PREFIX=reports
export RELEASE_ID=dev-20261111-1

aws sts get-caller-identity
aws eks describe-cluster --region "$AWS_REGION" --name "$EKS_CLUSTER" \
  --query 'cluster.{arn:arn,version:version,status:status,endpoint:endpoint}'
```

출력된 계정 ID가 제공받은 계정 ID와 일치하는지 확인한다.

```bash
aws eks update-kubeconfig --region "$AWS_REGION" --name "$EKS_CLUSTER" --alias "$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" auth can-i create deployments -n "$K8S_NAMESPACE"
kubectl --context "$KUBE_CONTEXT" auth can-i create jobs -n "$K8S_NAMESPACE"
kubectl --context "$KUBE_CONTEXT" auth can-i create secrets -n "$K8S_NAMESPACE"
```

namespace가 제공되면 그대로 사용한다. 새로 만들 권한을 받은 경우에만 `kubectl --context "$KUBE_CONTEXT" create namespace "$K8S_NAMESPACE"`를 실행한다. 아래 모든 kubectl 명령은 명시한 context를 사용한다.

## 5. Terraform으로 관리할 범위 선택

`terraform/terraform.tfvars.example`과 `terraform/backend.hcl.example`을 각각 `.example`이 없는 이름으로 복사해 실제 값을 채운다. 이 두 파일과 plan·state 파일은 gitignore 대상이다. `.terraform.lock.hcl`은 버전 관리에 포함한다.

| 받은 환경 | 설정 |
|---|---|
| EKS·S3·ECR·배치 역할 연결을 모두 제공자가 관리 | 세 관리 플래그를 모두 `false`. Terraform은 기존 자원을 조회하고 정책 제안만 출력 |
| S3·ECR은 제공, Pod Identity 연결을 팀이 담당 | `manage_batch_identity = true`; 기존 역할이 있으면 `existing_batch_role_arn` 입력 |
| S3·ECR도 팀이 새로 생성 | 생성 권한을 확인한 자원의 `create_reports_bucket`·`create_ecr_repository`만 `true` |

`manage_batch_identity = true`이고 기존 역할 ARN이 없으면 배치 IAM 역할과 정책도 생성한다. 이때 역할 생성/정책 설정, Pod Identity 연결, `iam:PassRole` 권한이 필요하다. 제공받은 기존 역할을 사용하면 그 역할의 trust/권한 정책은 제공자가 이 구성의 출력과 일치시키고, Terraform은 연결만 만든다.

**EKS·VPC·노드·RDS 생성은 포함하지 않는다.** 이번에 어떤 자원을 제공받는지 확정되지 않았기 때문에 공유 인프라의 소유권을 유지한다. 기존 S3·ECR의 정책을 이 Terraform이 덮어쓰지도 않는다. 기존 버킷의 비공개·암호화·버전 관리와 ECR 태그 정책은 제공자와 확인한다.

state 버킷은 앱 보고서 버킷과 별도로 제공자가 먼저 준비한다. 버전 관리·암호화를 켜고 접근을 팀 운영자에게 제한한다. S3의 `use_lockfile = true`를 사용한다. state 객체에는 Get/Put, `.tflock`에는 Get/Put/Delete, 필요한 prefix 조회 권한이 있어야 한다. state는 민감 정보를 포함할 수 있으므로 Git에 넣지 않는다.

```bash
terraform -chdir=deploy/terraform init -backend-config=backend.hcl -reconfigure
terraform -chdir=deploy/terraform plan -out=dev.tfplan
# plan의 대상 계정·생성/변경/삭제 항목을 확인한 뒤 실행한다.
terraform -chdir=deploy/terraform apply dev.tfplan
terraform -chdir=deploy/terraform output connection
```

아직 원격 state 없이 로컬 검사만 했다면 위 `-reconfigure`로 원격 backend를 초기화한다. 실제 관리 중인 로컬 state가 있는 별도 환경을 원격으로 옮기는 경우에는 state 이관 절차를 먼저 진행한다.

IAM 권한이 없다면 `batch_policy_json`·`batch_trust_policy_json` 출력과 namespace·`demurrage-batch` 이름을 제공자에게 전달한다. 이 경우 연결까지 준비됐다는 확인을 받은 뒤 수동 배치를 실행한다. KMS 버킷이면 `reports_kms_key_arn`과 키 정책의 접근 허용도 필요하다.

## 6. 이미지 빌드와 ECR push

```bash
export ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
export IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:${RELEASE_ID}"
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"
docker buildx build --platform linux/amd64,linux/arm64 --tag "$IMAGE_URI" --push .
```

고정 태그는 이전에 push하지 않은 배포 버전을 사용한다. 다중 아키텍처 빌드는 개발 PC와 EKS 노드 CPU가 달라도 실행할 수 있게 한다. 제공자가 단일 아키텍처를 지정하면 그 플랫폼만 빌드해도 된다. CI의 `make test`·`make verify`·컨테이너 smoke 검증을 통과한 소스에서 이미지를 만든다.

## 7. DB 접속 Secret과 CA 준비

```bash
cp deploy/database.env.example deploy/database.env
```

파일을 편집해 제공받은 PostgreSQL URL을 넣는다. 기본 예시는 `sslmode=verify-full`과 CA 파일을 사용한다. RDS라면 공식 CA bundle을 받을 수 있고, 다른 PostgreSQL이면 제공자의 CA를 사용한다.

```bash
curl --fail --location \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  --output deploy/rds-ca.pem
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" create configmap demurrage-db-ca \
  --from-file=rds-ca.pem=deploy/rds-ca.pem --dry-run=client -o yaml | \
  kubectl --context "$KUBE_CONTEXT" apply -f -
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" create secret generic demurrage-secrets \
  --from-env-file=deploy/database.env --dry-run=client -o yaml | \
  kubectl --context "$KUBE_CONTEXT" apply -f -
```

이 Secret은 초기 수동 연결용이다. 팀의 Secrets Manager/External Secrets 연동이 제공되면 같은 Secret 이름·key를 유지해 교체할 수 있다. DB Secret의 변경은 환경변수에 자동 반영되지 않으므로 `kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" rollout restart deployment/demurrage-api`로 재시작한다.

현재 `Store`는 시작 시 테이블과 append-only 트리거를 만든다. 초기 DB 계정은 해당 schema에 테이블·함수·트리거를 만들 권한이 필요하다. 최초 연결 후에는 별도 마이그레이션과 실행 계정 분리가 다음 작업이다. DB 보안 그룹·접속 경로도 확인한다. URL만으로 네트워크가 연결되지는 않는다.

## 8. YAML 렌더링 → 서버 검사 → 배포

```bash
.venv/bin/python scripts/render_eks.py \
  --image "$IMAGE_URI" --reports-bucket "$REPORTS_BUCKET" \
  --region "$AWS_REGION" --namespace "$K8S_NAMESPACE" --reports-prefix "$REPORTS_PREFIX" \
  --output deploy/rendered/eks.yaml
kubectl --context "$KUBE_CONTEXT" apply --dry-run=server -f deploy/rendered/eks.yaml
kubectl --context "$KUBE_CONTEXT" apply -f deploy/rendered/eks.yaml
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" rollout status deployment/demurrage-api --timeout=300s
```

렌더러는 잘못된 리전·ECR 주소·`latest`·자리표시자·namespace를 거부한다. 설정 ConfigMap 이름에는 내용 해시가 붙어 설정 변경이 Pod 템플릿 변경으로 이어진다. 생성 YAML에는 DB URL이 들어가지 않는다.

현재 API에는 사용자 인증이 없으므로 Service는 ClusterIP다. 연결 검증은 아래처럼 로컬로 접속한다. 첫 터미널에서 실행하고 두 번째 터미널에서 smoke를 실행한다.

```bash
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" port-forward service/demurrage-api 8000:80
```

```bash
.venv/bin/python scripts/smoke.py http://localhost:8000
```

## 9. 배치 수동 실행 → S3 확인 → 예약 활성화

```bash
export JOB_NAME="demurrage-report-$(date +%s)"
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" create job \
  --from=cronjob/demurrage-daily-report "$JOB_NAME"
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" wait \
  --for=condition=complete "job/$JOB_NAME" --timeout=620s
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" logs "job/$JOB_NAME"
aws s3api list-objects-v2 --bucket "$REPORTS_BUCKET" --prefix "${REPORTS_PREFIX}/" \
  --query 'Contents[].[Key,Size]' --output table
```

성공 로그는 `status: created` 또는 `already_exists`와 S3 저장 위치를 보여 준다.

`reports/<한국 날짜>/<시나리오>/<내용 식별자>.json`에는 입력, 계산 결과, 규칙/엔진 버전, 실행 검사, 보고서 HTML/Markdown과 메일 초안이 함께 들어간다. S3에는 JSON 하나를 원자적으로 저장하므로 파일 묶음의 일부만 성공하는 상태를 피한다. 점검하는 사람에게는 별도의 S3 List/Get 권한이 필요하다. 배치 역할에는 쓰기 권한만 준다.

수동 Job의 성공·S3 객체·계산 결과를 확인한 뒤 같은 렌더링 명령에 `--enable-cron`을 추가해 다시 적용한다. 이제 매일 09:00에 실행한다. 600초의 시작 허용 범위 때문에 활성화 시각이 예약 직후이면 해당 회차가 실행될 수 있다. 다시 중지할 때는 플래그 없이 렌더링해 적용한다. 이미 실행 중인 Job은 별도로 확인한다.

배치에는 DB 비밀번호와 LLM 키를 주지 않는다. 기본 배치는 DB 실행 목록에 기록되지 않고 S3·Pod 로그에 남는다. 사람이 API에서 수행하는 승인·확정 기록은 PostgreSQL에 남는다. 두 기록의 통합이 필요하면 작업 ID/상태 API를 별도로 구현한다.

## 10. 장애 확인과 되돌리기

| 증상 | 먼저 확인할 것 |
|---|---|
| `ImagePullBackOff` | 이미지 주소·태그·CPU 플랫폼·ECR 접근·노드 pull 권한 |
| `CreateContainerConfigError` / volume mount 실패 | `demurrage-secrets`의 DATABASE_URL, `demurrage-db-ca` ConfigMap |
| API 시작 실패·`/readyz` 실패 | DB 주소·비밀번호·CA·DDL 권한·5432 네트워크·로그 |
| Job의 `ClientError` | Pod Identity Agent/연결·역할 trust·S3 prefix·버킷 소유자·KMS 키 정책 |
| Job의 `NoCredentialsError` | 서비스 계정 연결, 지원 노드 종류, Agent/EKS Auth API 접속 |
| Job의 `ValueError` | 배포 설정·시나리오 ID·후보 생성·실행 검사; 로컬 명령으로 재현 |
| `Pending` / `OOMKilled` | namespace quota·노드 가용량·CPU/메모리 사용량 |

API는 이전 이미지 버전으로 다시 렌더링·적용해 되돌린다. `rollout undo`를 사용할 수도 있지만 환경값까지 재현하려면 이전 배포의 이미지·렌더링 입력값을 함께 보관해야 한다. DB 데이터는 이미지 롤백으로 되돌아가지 않는다. 초기 Recreate 배포에는 짧은 중단이 발생한다.

실패 Job 확인:

```bash
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" get pods,jobs,cronjobs
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" describe "job/$JOB_NAME"
kubectl --context "$KUBE_CONTEXT" -n "$K8S_NAMESPACE" logs "job/$JOB_NAME" --all-containers=true
```

Pod 로그의 중앙 수집·실패 알림은 연결 후 별도로 확인한다. Job 보존 개수와 7일 TTL은 중앙 로그 보관을 대신하지 않는다. namespace 삭제나 `terraform destroy`는 공유 자원까지 영향을 줄 수 있으므로 일반적인 앱 되돌리기 절차로 사용하지 않는다.

## 공식 문서

- [CronJob 실행 정책·시간대·제약](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [Startup / readiness / liveness probe](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [EKS 사용자 접근 권한](https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html)
- [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html), [역할 trust policy](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-role.html)
- [S3 조건부 PutObject](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html)
- [Terraform S3 backend와 잠금](https://developer.hashicorp.com/terraform/language/backend/s3)
- [Terraform provider 모의 테스트](https://developer.hashicorp.com/terraform/language/tests/mocking)
- [RDS TLS와 인증서](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html)
