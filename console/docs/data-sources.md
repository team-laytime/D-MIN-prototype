# 선박 정보는 어디서 오나 — AIS · PORT-MIS 조사

- 작성: 2026-11-12 · 선박 카드(제원 · 항행 상태 · AIS 갱신 · 시설 사용 · ETA · 목적지)를 실제 솔루션에서 채우려면 어디서 받아야 하는지 정리했다.
- 링크는 모두 직접 열어 확인한 것만 적었다. 공공데이터포털 API는 활용 신청 뒤 받은 인증키(serviceKey)가 있어야 부를 수 있고, 실제 호출은 아직 하지 않았다.

## 결론

1. **ETA와 목적지는 AIS의 '항해 정보'에 있다.** AIS 메시지 5번(정적 · 항해 정보)에 목적항(DESTINATION)과 도착 예정 시각(ETA)이 들어 있다. 다만 **선장이 손으로 입력하는 값**이라 비어 있거나 늦게 고쳐질 수 있다([VesselFinder API 문서](https://api.vesselfinder.com/docs/response-ais.html): "manually entered by the Master"). 그래서 화면은 AIS ETA와 계획 ETA(대리점 통보)를 나란히 두고, 2시간 넘게 다르면 '다시 계산 필요'를 띄운다 (N-002).
2. **위치 · 속력 · 침로 · 항행 상태는 AIS 동적 정보**다. 울산항 안쪽은 울산항만공사 공공 API로 받을 수 있다.
3. **입항 · 접안 · 이안 시각, 하역 시작 · 완료는 PORT-MIS 신고 자료**다. 울산항만공사가 공공 API로 연다.
4. **시설 신청 · 배정 · 사용(PORT-MIS 시설사용 허가)** 은 공개 API를 찾지 못했다. 울산항만공사 PortWise 화면에서만 보인다. 현업(SEAGATE · PORT-MIS) 연계로 받아야 하는지 멘토에게 확인할 항목이다.
5. 첫 portwise는 PortWise 화면이 부르는 내부 엔드포인트를 서버에서 대신 불러 이 값을 가져왔다([sk-portwise 첫 커밋의 `lib/upa.js` · README](https://github.com/minkyu-k530/sk-portwise)). 비공식 방식이고 README에도 "운영 용도로 쓰려면 정식 API와 이용 승인으로 바꿔야 한다, 약관이 자동화 수집을 제한한다"고 적혀 있다. **실제 솔루션은 아래 정식 경로를 쓴다.**

## 선박 카드 항목 → 출처

| 카드 항목 | 원래 자료 | 정식으로 받는 곳 |
|---|---|---|
| 위치 · 속력(SOG) · 침로(COG) · 항행 상태 · 흘수 | AIS 동적 정보 | [울산항만공사_항내 선박위치정보](https://www.data.go.kr/data/15156631/openapi.do) — 호출부호 · 입항연도 · 항차 · 선박명 · 경위도 · 대지속력 · 대지침로 · 선회율 · 선박흘수 · 운항상태 (REST, JSON/XML, 무료) |
| 목적지 · ETA | AIS 항해 정보 (선장 입력) | 공공 API에서 찾지 못함 → 상용 AIS: [aisstream.io](https://aisstream.io/documentation) `ShipStaticData` (WebSocket, 키는 서버에만) 또는 [VesselFinder API](https://api.vesselfinder.com/docs/response-ais.html) `DESTINATION` · `ETA` |
| 길이 · 폭 | AIS 정적 정보 | AIS 안테나 거리 A+B = 길이, C+D = 폭 ([VesselFinder 문서](https://api.vesselfinder.com/docs/response-ais.html)) |
| DWT · GT 같은 제원 | 선박 원부 · 계약 | 계약 · 대리점 자료(업무 DB). 울산항만공사 '선박제원정보'는 이번에 열어 보지 못했다 |
| 입항 · 접안 · 투묘 · 양묘 · 이안 · 출항 시각, 시설 | PORT-MIS 신고 | [울산항만공사_항만 내 선박 운항정보](https://www.data.go.kr/catalog/15156628/openapi.json) — 호출부호 · 입항연도 · 항차 · 입출항일시 · 시설제원코드 · 작업일시 |
| 하역 시작 · 완료 (과거 Rate → 작업 시간 추정, P10) | PORT-MIS 하역 기록 | [울산항만공사_선박 하역정보](https://data.go.kr/catalog/15156639/openapi.json) — `B551938/UnloadRcdInfoService` |
| 화물 · 시설 · 톤수 | 수출입 화물 신고 | [울산항만공사_울산항 수출입 화물정보](https://data.go.kr/catalog/15156637/openapi.json) — `B551938/IntgCagInfoService` |
| 부두 제원 · 좌표 | 항만 시설 | [울산항만공사_위치기반 부두운영시설정보](https://www.data.go.kr/catalog/15156713/openapi.json) — `B551938/GisBaseHrbrFcltDtlInfoService` (시설코드 · 길이 · 수심 · 경위도) |
| 시설 신청 · 배정 · 사용 | PORT-MIS 시설사용 허가 | 공개 API 못 찾음 — 현업 연계 확인 필요 |
| 기상 악화 → 부두 제약 시간 제안 | 국립해양조사원 지수 | [항만해양지수](https://www.data.go.kr/catalog/15142502/openapi.json) · [선박운항지수](https://www.data.go.kr/catalog/15156036/openapi.json) (멘토링 12쪽: 기상은 '부두 제약 시간 설정'으로 대체) |

## 묶는 열쇠

- 울산항만공사 API들은 **호출부호 + 입항연도 + 항차**로 한 번의 입항을 가리킨다. AIS는 **MMSI**가 열쇠다. 선박 한 척에 MMSI · IMO · 호출부호를 함께 저장해 두고 이어 붙인다.
- 우리 입항 건(i)과 PORT-MIS 항차를 1:1로 잇는 표가 업무 DB에 있어야 한다.

## 주의할 것

- 공공데이터포털 페이지에 업데이트 주기가 '일간'과 '실시간'으로 엇갈려 적힌 곳이 많다. 실제로 불러 갱신 간격을 재야 한다 (화면의 '데이터 연계 상태'가 그 값을 보여 줄 자리다).
- aisstream은 키를 브라우저에서 쓰지 못하게 되어 있고, 계정당 연결 3개, 가동률 보장이 없다. 시연 보조로는 쓸 수 있지만 운영 근거로 삼기 어렵다.
- AIS ETA는 틀릴 수 있다는 전제로 다룬다. 계산 입력은 계획 ETA(통보)이고, AIS ETA는 '바뀌었는지 감지'에 쓴다.
