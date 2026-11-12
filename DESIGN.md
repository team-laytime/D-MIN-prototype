---
name: D-MIN 체선료 비교
description: 울산 CLX 접안 순서·체선료 비교 업무 포털 (프로토타입)
colors:
  portal-red: "#d6202f"
  portal-red-deep: "#b81a27"
  portal-red-wash: "#fdf0f1"
  ink: "#222222"
  ink-muted: "#666666"
  ink-faint: "#999999"
  table-rule: "#555555"
  slate-navy: "#2b3445"
  link-blue: "#1f4e9c"
  page-gray: "#f1f2f4"
  cell-gray: "#f4f5f7"
  line: "#e6e7ea"
  line-strong: "#d6d8dc"
  paper: "#ffffff"
  ok-green: "#2e7d32"
  wait-amber: "#c77700"
  alert-red: "#e02424"
  unknown-violet: "#6a4fb3"
  notice-yellow: "#fff8e1"
  footer-charcoal: "#3a3a3a"
typography:
  page-title:
    fontFamily: "Noto Sans KR, Apple SD Gothic Neo, Malgun Gothic, sans-serif"
    fontSize: "23px"
    fontWeight: 400
    letterSpacing: "-0.03em"
  section-title:
    fontFamily: "Noto Sans KR, Apple SD Gothic Neo, Malgun Gothic, sans-serif"
    fontSize: "16px"
    fontWeight: 700
  gnb:
    fontFamily: "Noto Sans KR, Apple SD Gothic Neo, Malgun Gothic, sans-serif"
    fontSize: "16px"
    fontWeight: 500
  body:
    fontFamily: "Noto Sans KR, Apple SD Gothic Neo, Malgun Gothic, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  table-head:
    fontFamily: "Noto Sans KR, Apple SD Gothic Neo, Malgun Gothic, sans-serif"
    fontSize: "12.5px"
    fontWeight: 600
rounded:
  none: "0px"
  control: "2px"
  pill: "15px"
spacing:
  section: "28px"
  cell-y: "6px"
  cell-x: "12px"
  page-x: "28px"
components:
  button-primary:
    backgroundColor: "{colors.portal-red}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    height: "30px"
    padding: "0 12px"
  button-primary-hover:
    backgroundColor: "{colors.portal-red-deep}"
  button-default:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "30px"
    padding: "0 12px"
  table-header-cell:
    backgroundColor: "{colors.cell-gray}"
    textColor: "{colors.ink}"
    typography: "{typography.table-head}"
    height: "38px"
  input:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.control}"
    height: "30px"
  gnb-pill:
    backgroundColor: "#888c92"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    height: "30px"
---

# Design System: D-MIN 체선료 비교

## Overview

**Creative North Star: "The Terminal Back Office"**

국내 정유·항만 사내 업무 포털의 문법을 그대로 따른다. 사용자가 지정한 기준 화면은 BerthDesk 접안 계획 콘솔이다. 스케줄러가 하루에도 여러 번 여는 화면이라 장식보다 표의 밀도와 읽는 속도가 먼저다. 회색 바탕 위에 진한 윗선을 가진 흰 표가 정보의 단위이고, 빨강은 주 동작과 선택, 위반에만 쓴다.

화면 구조는 상단 유틸 바 · GNB · 왼쪽 LNB · 본문 · 어두운 푸터로 고정한다. 본문은 제목과 브레드크럼, 계획 흐름 단계, 요약 표, 노란 안내 띠, 구역 제목과 표 순서로 쌓는다. 카드, 그림자, 둥근 모서리, 연한 색 알약 같은 소비자 앱 표현은 쓰지 않는다(사용자 지적: "클로드스럽다").

**Key Characteristics:**
- 진한 2px 윗선 + 회색 헤더 칸의 표가 기본 단위
- 빨강 1색 강조, 상태는 배경 없이 글자색과 굵기
- 직각에 가까운 모서리(2px), 그림자 없음
- 업무 도구 말투: 명사형 라벨, 설명은 합니다체 한 줄

## Colors

빨강 한 색과 회색 계열 중립, 그리고 뜻이 정해진 상태 색.

### Primary
- **Portal Red** (#d6202f): 주 버튼, 현재 GNB·LNB 메뉴, 현재 단계, 선택 행의 배경(#fdf0f1), 브랜드 워드마크.

### Neutral
- **Ink** (#222222): 본문 글자.
- **Table Rule** (#555555): 표와 구역 본문의 2px 윗선.
- **Slate Navy** (#2b3445): 활성 탭, 지도 시간 막대의 재생 버튼, SK 부두 표식.
- **Page Gray** (#f1f2f4): 페이지·LNB 바탕. **Cell Gray** (#f4f5f7): 표 머리 칸·라벨 칸.
- **Line** (#e6e7ea) / **Line Strong** (#d6d8dc): 행 구분선 / 표 아랫선·입력 테두리.
- **Footer Charcoal** (#3a3a3a): 하단 푸터.

### Named Rules
**The Meaning-Only Color Rule.** 초록은 정상·절감, 주황(#c77700)은 대기·해당, 빨강(#e02424)은 체선 발생·위반, 보라(#6a4fb3)는 판단 불가, 파랑(#1f4e9c)은 링크·작업 중·변경 값. 뜻이 없는 곳에 색을 칠하지 않는다.

## Typography

**Body Font:** Noto Sans KR (Apple SD Gothic Neo, Malgun Gothic 대체)

**Character:** 국내 업무 시스템에서 가장 익숙한 고딕. 크기 단계는 작고 굵기로 위계를 만든다.

### Hierarchy
- **Page Title** (400, 23px): 페이지 제목. 굵게 하지 않는다.
- **GNB** (500, 16px): 상단 주 메뉴.
- **Section Title** (700, 16px): 구역 제목. 옆에 12px 회색 설명을 붙인다.
- **Body** (400, 13px, 1.5): 표 칸과 본문.
- **Table Head** (600, 12.5px): 가운데 정렬 머리 칸.
- 숫자는 `tabular-nums`, 금액은 오른쪽 정렬.

## Layout

- 유틸 바 30px · GNB 82px(좌우 48px 여백) · LNB 260px · 본문 좌우 28px · 본문 최대 1400px.
- 구역 사이 28px. 구역 = 제목 줄(아래 8px) + 흰 본문(2px 윗선).
- 계획 흐름 화면은 제목 아래 단계 표시(1. 입력 확인 › … › 5. 보고서 작성), 현재 단계 빨강 굵게.
- 최소 너비 1280px(데스크톱 업무 화면).

## Elevation & Depth

평면이다. 깊이는 선과 회색 단계로만 나타낸다. 예외는 겹쳐 뜨는 요소뿐이다: 산출 근거 패널(왼쪽 1px 선 + 어두운 막), 사용법 안내 카드(위 2px 빨강 선 + `0 8px 24px rgba(0,0,0,0.25)`).

## Shapes

모서리 2px(버튼·입력), 표와 구역은 0. GNB 오른쪽 시나리오 선택과 사용법·사이트맵만 15px 알약 모양.

## Components

### Buttons
- **Shape:** 2px, 높이 30px, 12.5px 글자.
- **Primary:** Portal Red 바탕 흰 글자, 화면당 주 동작 하나.
- **Default:** 흰 바탕 #cfd2d6 테두리.
- **Ghost:** 파랑 밑줄 링크(표 안 "보기" 등).

### Status text (chips)
- 해당·해당 없음·판단 불가·위반은 배경 없는 굵은 색 글자. 중립 태그만 회색 테두리 20px.

### Tables
- 2px #555 윗선, #f4f5f7 머리 칸(가운데 정렬), 칸 사이 1px 세로선, 행 높이 38px, 선택 행 #fdf0f1.

### Inputs / Fields
- 흰 바탕 #cfd2d6 1px, 2px 모서리, 높이 30px(표 안 26px). 포커스는 테두리 #888.

### Navigation
- GNB: 가운데 정렬 메뉴, 현재 묶음 빨강. LNB: 영문 대문자 묶음 이름 + 사각 펼침 표식, 펼친 묶음은 흰 바탕·왼쪽 2px 빨강 선의 하위 메뉴.

### Notice
- 노란 띠(#fff8e1, #f0d58a 테두리) + 원형 경고 아이콘, 오른쪽 끝 밑줄 동작 링크. 발효 중인 경보는 빨간 띠.

### Port map (signature)
- 회색 베이스맵(Esri Light Gray) 위 SK 부두 사각 표식(흰 바탕 남색 테두리, 접안 중이면 남색 채움), 선박은 상태 색 화살 모양, 정박지는 점선 원. 지도 아래에 흰 시간 막대(재생·±1시간·슬라이더, 빨간 구간=기상 악화).

## Do's and Don'ts

### Do:
- **Do** 정보를 표로 묶고 표마다 2px 윗선을 둔다.
- **Do** 주 동작은 화면당 빨간 버튼 하나로 둔다.
- **Do** 라벨은 명사형, 설명은 합니다체 한 줄로 쓴다.
- **Do** 모든 화면에 "가상 데이터"와 "의사결정 보조용"을 남긴다(푸터).

### Don't:
- **Don't** 둥근 카드, 그림자 카드, 연한 배경 알약 칩을 쓰지 않는다.
- **Don't** "~해요"체 안내문을 늘어놓지 않는다.
- **Don't** 제목 위에 작은 꼬리표(eyebrow)를 달지 않는다.
- **Don't** 이모지나 유니코드 기호를 아이콘 대신 쓰지 않는다(lucide 아이콘 사용).
