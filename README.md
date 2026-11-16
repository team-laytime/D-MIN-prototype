# D-MIN 프론트 프로토타입

울산 CLX 선박 체선료 최적화 Agent의 화면 흐름을 확인하려고 만든 버릴 코드다. 실제 프론트는 `D-MIN-front`에서 만든다.

- 데모: https://team-laytime.github.io/D-MIN-prototype/
- 계정: 처음 화면에서 로그인한다(비밀번호 `1234`). 스케줄러(`scheduler`)는 일정을 짜고 확정하고, 이용자(`user`)는 확정된 일정만 본다. 각 계정에는 자기 메뉴만 보인다.
- 흐름(스케줄러): 홈 → 시나리오 입력 → 후보 비교 → 리스크·확정 → 보고서 초안 → 검증. 오른쪽 위 「사용법」은 화면을 하나씩 짚는 안내 투어다. 확정한 뒤 로그아웃하고 이용자로 들어가면 그 일정이 보인다.

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
