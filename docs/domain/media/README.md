# 설명 영상 4편 — 체선료 입문

- 작성일: 2026-11-02 (4편 추가: 2026-11-05)
- 형식: 1280×720, 30fps, H.264 + AAC. 한국어 나레이션(macOS 음성 Yuna)과 자막(장면 캡션) 포함. 데이터는 전부 가상이고 규칙값은 가정이다.

| 파일 | 제목 | 길이 | 내용 |
|---|---|---|---|
| `01-laytime-101.mp4` | 레이타임 101 | 약 2분 9초 | 레이타임·체선료·조출료 개념, 요율 감각, 두 겹 계약(back-to-back), SK 비용 경로 |
| `02-nor-clock.mp4` | NOR과 시계가 도는 순간 | 약 2분 48초 | NOR, 통지시간, 개시 규칙(min), 대기 산입, 이동 제외, 야간 접안 제한, 종료, 체선, 반액 |
| `03-calc-walkthrough.mp4` | 체선료 계산 따라하기 | 약 2분 41초 | 예제 TC-02를 SOF → 개시 → 종료 → 공제 → 체선료 → 계산서 순으로 손계산, Agent의 역할 |
| `04-optimization-flow.mp4` | 배의 여정에서 후보 비교까지 | 약 5분 46초 | 배 한 척의 여정(9단계)과 시계, 두 척 사례(순서 A 52,000달러 대 순서 B 6,000달러), 기준안(베이스라인)과 줄인 금액, 제약으로 후보 거르기, 도우미의 7단계, 후보 카드, 검증, 전체 대 한 선박. 수치는 팀 손계산 정답 SC-01(`../../requirements/09-first-steps.md`) |

권장 시청 순서: 01 → 시뮬레이터 체험 → 02 → 03 → `../04-worked-examples.md`로 직접 계산 → 04(프로젝트가 무엇을 최적화하는지). 처음이라면 04를 먼저 봐도 큰 그림이 잡힌다.

## 보는 방법

| 방법 | 어떻게 | 비고 |
|---|---|---|
| 어디서든(웹·모바일) | https://claude.ai/artifact/D8Tdb7BezkJKefgi13bCN4 | 비공개 아티팩트. 팀원은 Share 설정 뒤 열람 가능. 영상 파일은 아티팩트 자산으로 올라가 있음 |
| 이 폴더에서 바로 | `01-laytime-101.mp4` 등을 더블클릭(QuickTime) | 가장 확실 |
| 로컬 미리보기 페이지 | 아래 명령 뒤 http://localhost:8765/media/index.html | `.claude/launch.json`의 `domain-docs-preview` 설정과 같음 |

```bash
python3 -m http.server 8765 --directory docs/domain
```


## 다시 만들기

영상은 `src/`의 HTML 애니메이션을 헤드리스 Chrome으로 프레임 렌더해 ffmpeg로 묶고, 장면별 TTS 나레이션을 입힌 것이다. 대본이나 그림을 고치면 같은 명령으로 다시 뽑는다.

필요한 것: macOS(TTS `say`, 음성 **Yuna** 설치: 시스템 설정 → 손쉬운 사용 → 콘텐츠 말하기 → 시스템 음성 → 한국어), Google Chrome, ffmpeg, Node.js 18 이상.

```bash
cd docs/domain/media/src && npm install
```

```bash
node build.js v1 --sheet
```

```bash
node build.js v1
```

- `--sheet`는 장면별 정지 프레임 3장만 `out/v1-sheet/`에 뽑아 레이아웃을 확인하는 모드다. 전체 렌더는 한 편에 3~6분 걸린다(`out/v1.mp4`).
- 4편은 `v4`다: `node build.js v4` (대본 `src/scripts/v4.json`, 그림 `src/v4.html`). 4편은 장면마다 나레이션 진행률(`P(lt, dur)`)에 맞춰 요소가 나타나서, 대본 길이를 고쳐도 그림이 따라간다.
- 대본: `src/scripts/v1.json`. `caption`은 화면 자막, `tts`는 읽는 문장(숫자·약어는 한글로 풀어 쓴다). 장면 길이는 나레이션 길이에 맞춰 자동으로 정해지고 `minDur`가 하한이다.
- 그림: `src/v1.html`의 `registerScene(id, draw)`에서 장면별로 `lt`(장면 시작 후 초)에 따라 요소를 드러낸다. 시간축 그림은 `src/lib.js`의 `Track`을 쓴다.
- 음성 품질을 바꾸려면 `scripts/*.json`의 `voice`를 바꾸거나, 직접 녹음한 wav를 `tts/` 캐시 파일 대신 넣는다(파일명은 텍스트 해시라 `build.js`의 캐시 로직을 참고).
- 시뮬레이터 화면 녹화가 아니라 전용 애니메이션이므로, 규칙·수치를 바꾸면 영상과 `../04-worked-examples.md`를 함께 고친다.
