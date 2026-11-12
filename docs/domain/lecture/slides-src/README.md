# 슬라이드 덱 소스 (체선료 도메인 집중 강의)

- 게시된 덱: https://claude.ai/artifact/44FrZEQDmBHaZsr7ayrbeU (Slides 아티팩트, 비공개. 팀원은 Share 설정 뒤 열람·PDF/PPTX 내려받기 가능)
- `deck.json`: 슬라이드 순서(`order`), 섹션 개요, 서체 정의
- `slides/<id>.html`: 슬라이드 1장 = `<section id>` 1개. 1920×1080 캔버스, 인라인 스타일, 마지막 `<aside>`가 발표자 노트
- 수정 방법: 해당 `slides/<id>.html`을 고친 뒤, 같은 아티팩트 URL로 다시 게시한다(Claude에게 "덱의 m3-rules 슬라이드를 … 로 고쳐 게시해 줘"라고 요청하면 이 소스를 기준으로 반영한다). 직접 편집은 아티팩트 페이지에서도 가능하다.
- 슬라이드 ↔ 강의 노트 매핑은 `../09-teaching-guide.md` §3
