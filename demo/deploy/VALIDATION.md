# 사전 검증 기록

검증일: 2026-11-11. 실제 AWS 자원 생성·EKS 배포·S3 접속은 수행하지 않았다.

| 검사 | 결과 |
|---|---|
| 전체 pytest | 109개 통과 |
| `demurrage verify --strict` | 정답 272/272칸, 후보 위반 0건, 완전 탐색 대조 통과 |
| Terraform 1.14.0 / AWS provider 6.72.0 | fmt·validate 통과 |
| Terraform mock plan | 5개 통과: 기존 자원 기본 조회, 역할 재사용, 선택적 생성, 자리표시자 계정/다른 계정 역할 거부 |
| Kustomize 렌더링 | API·배치의 같은 이미지/설정 참조, 설정 변경 시 이름 해시 변경, CronJob 활성화 선택, 이미지 digest 검사 통과 |
| Kubernetes 스키마 | kubeconform 0.7.0 / Kubernetes 1.34.0 strict: 6개 자원 유효, 오류·건너뜀 0개 |
| S3 API 단위 검사 | 실제 네트워크 없이 SDK Stubber로 조건부 PutObject·버킷 소유자 전달·412 중복·403/409 실패 확인 |
| Linux ARM64 이미지 | Docker 빌드, 읽기 전용 API + 별도 PostgreSQL healthy, `/healthz`·`/readyz`·smoke 통과 |
| 이미지 안의 엔진 | 정답 검증 통과 |
| 이미지 안의 배치 | 읽기 전용 root에서 로컬 저장 created → 재실행 already_exists 확인 |
| 테스트 환경 정리 | 별도 compose 프로젝트의 컨테이너·볼륨 정리 완료 |
| GitHub 워크플로 | 루트 위치·YAML 문법 확인. 원격 CI 실행은 미수행 |

Terraform mock 검사는 AWS 권한이나 실제 자원 존재를 확인하지 않는다. Kubernetes 스키마 검사는 대상 EKS의 admission 정책·quota·노드·네트워크를 확인하지 않는다. Docker의 로컬 PostgreSQL 검사는 실제 RDS TLS/보안 그룹 연결을 확인하지 않는다.

자원을 받은 뒤 [배포 가이드](README.md)에 따라 계정·권한 확인, 서버 dry-run, 이미지 pull, DB TLS 연결, Pod Identity 자격 증명, 실제 S3 조건부 저장, 다음 예약 회차, 중앙 로그/알림을 순서대로 검증한다.
