# D-MIN 프론트 프로토타입

울산 CLX 선박 체선료 최적화 Agent의 화면 흐름을 확인하려고 만든 버릴 코드다. 실제 프론트는 `D-MIN-front`에서 만든다.

- 데모: https://team-laytime.github.io/D-MIN-prototype/
- 흐름: 홈 → 시나리오 입력 → 후보 비교 → 리스크·선택 → 보고서 초안 → 검증, 그리고 Agent 워크플로우

```bash
bun install && bun run dev   # http://localhost:5174
```

- 데이터는 전부 가상이다(`src/lib/scenarios.js`, 시나리오 S1~S3).
- 계산·탐색은 화면 확인용으로 브라우저에서 돌린다(`src/lib/engine.js`). 실제 구현에서는 Spring 계산 모듈이 맡는다.
- 6척 × 순서 720가지 × 부두 배정 8가지 = 5,760안을 전부 돌려 후보 3개를 고른다.
- `src/lib/answerSet.js`의 손계산 값은 엔진과 따로 Python Decimal(HALF_UP)로 구했다.
- 보고서 초안은 LLM 없이 템플릿으로 만든다.
- `요구사항-수정안.md`는 프로젝트 소개 문서를 정리한 안이다.
- `main`에 푸시하면 GitHub Actions가 Pages로 배포한다.
