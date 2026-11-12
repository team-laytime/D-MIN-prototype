# 13. 수리계획법 — 변수와 식 (두 타입)

- 작성 2026-11-10 · 접안 계획 문제를 변수·목적함수·제약식으로 적어 범용 솔버(HiGHS)로 풀었다. 기준 문서에 따라 두 타입으로 나눴다.
- 수리계획법이란: 정할 수 있는 값(변수)을, 규칙(제약식)을 지키면서, 어떤 숫자(목적함수)가 가장 작아지게 정하는 방법. programming은 계획 짜기라는 뜻이다. 예·아니오(0/1) 변수가 섞이면 혼합정수계획법(MILP)이고, 접안 순서가 그런 결정이라 우리 문제는 MILP다.

| | 타입 1 — 주제 설명 문서 기준 | 타입 2 — 멘토링 PPT 기준 |
|---|---|---|
| 문서 | [13a](13a-math-programming-brief.md) · [공유용 페이지](assets/13a-math-programming-brief.html) · [아티팩트](https://claude.ai/artifact/4MPxMzFbBBMBBgmazppw38) | [13b](13b-math-programming-ppt.md) · [공유용 페이지](assets/13b-math-programming-ppt.html) · [아티팩트](https://claude.ai/artifact/NPZ7cijznwkhU8CBtyz5aS) |
| 기준 | 과제 주제 설명 문서(원문 3절 기능 1·2·5, 6절) | 현업 멘토링 PPT 06~12쪽, 멘토 설명, 샘플 데이터 |
| 계산 근거 | 도착 일시 · 허용 시간 · 예상 작업 종료 시간 · 하루 체선료 | ETA·ETANR·LayCan·LayTime·Rate, Direction·Switching, 과거 실적 |
| 제약 | 부두별 접안 가능 제품 · 조석 · 일출·일몰 · 기상 · 한 부두 한 척 | 이전 선박·FIX · 야간 도선 · 동일 화물 그룹·부두 동시 접안 · 부두 제약 · 재고 (조석 제외) |
| 허용시간을 세는 시작 | 도착 + 통지시간과 접안 중 이른 때(계약 값) | 정박개시 갈래: Early Loading · LayCan Miss · 조기 도착 06/07시 · ETANR + 6h · Daylight |
| 기상 | 기상으로 기다린 시간 × 계약의 공제비율 | 기상체선 시간 ÷ 2 (정의는 확인 필요, 해석 3가지) |
| 결정변수 | u 시간창선택 · y 앞뒤순서 · t 접안시각 (같다) | u · y · t (같다) |
| 스크립트 | `scripts/milp_brief.py` | `scripts/milp_berth_plan.py` |
| 검증 | 손계산 정답 SC-01 일치, 가상 시나리오 기준안 $48,868 → 1안 $18,868, 무작위 300사례 완전 탐색과 일치, 위반 0 | 정답 2 + 시나리오 20: 21문제 엔진 탐색과 일치·1문제 더 낮음, 후보 63개 위반 0, S05 기준안 $69,142 → 1안 $47,919 |

두 타입 모두 핵심은 같다. **"이 시각에는 접안하지 못한다"는 규칙은 변수로 만들지 않고 시간창으로 미리 계산**하고, 솔버는 어느 창에 댈지(u), 누가 먼저인지(y), 몇 시에 댈지(t)만 정한다. 다른 점은 시간창과 정박개시를 만드는 규칙이 어느 문서에서 오느냐다.

공용 도구는 `scripts/milp_core.py`다. 솔버가 "최적"이라고 한 값도 그대로 믿지 않도록 두 설정으로 풀어 비교하고, 답은 모델과 따로 짠 계산식·검증기로 다시 확인한다. scipy가 필요해서 엔진(`src/demurrage`, 표준 라이브러리만)에는 넣지 않았다.

```bash
python3 demo/scripts/milp_brief.py              # 타입 1
python3 demo/scripts/milp_berth_plan.py         # 타입 2 (PPT 규칙)
```
