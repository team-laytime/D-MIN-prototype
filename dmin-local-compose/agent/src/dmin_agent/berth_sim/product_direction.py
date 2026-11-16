"""제품별 반입·반출 방향과 탱크 묶음.

선박의 방향은 엑셀 접안계획의 Biz 열을 그대로 쓴다:
  IM(수입) · DI(내수 매입) → 반입   /   EX(수출) · DO(내수 판매) → 반출
제품의 방향은 아래 표 (업계 일반 지식 기준 가정, 현업 확인 필요):
  반입    원유와 외부 원료
  반출    정유 · 석유화학 · 윤활유 · 특수 제품 (표에 없는 제품은 모두 반출)
  양방향  원료로 들이기도 하고 제품으로 내기도 하는 것
가상 화물은 선박 방향과 맞는 제품(또는 양방향 제품) 중에서만 고른다. 54척 모두 예외 없음.

탱크 묶음 (재고 제약 단위)
  원유        CR 제품 (CRUDE, L/S)
  반입 원료   원유가 아닌 반입 제품
  양방향      양방향 제품
  {분류} 반출  나머지 반출 제품을 제품 분류별로 (석유제품 · 화학 · 윤활유 · 특수)
"""

IN, OUT, BOTH = "반입", "반출", "양방향"

PRODUCT_DIRECTION: dict[str, str] = {
    # 원유
    "CRUDE": IN,
    "L/S(고유동점)": IN,
    # 외부 원료
    "기유(양하)": IN,  # '양하' = 하역
    "MEOH": IN,  # 메탄올: 정유 공정에서 나오지 않는 원료
    "C9+ARO (JX)": IN,  # JX(일본 공급사) 방향족 원료
    "UCO": IN,  # 폐식용유: 바이오 연료 원료
    # 원료 · 제품 양쪽
    "NAPH": BOTH,
    "LPG": BOTH,  # 정유 생산 + 가스 부두 수입
    "BUTENE": BOTH,
    "FO": BOTH,  # 출하가 주지만 벙커 · 원료로 들이기도 함
}

CLASS_LABEL = {"CR": "원유", "PP": "석유제품", "PC": "화학", "LB": "윤활유", "SP": "특수"}


def direction_of(cargo_group: str) -> str:
    return PRODUCT_DIRECTION.get(cargo_group, OUT)


def vessel_direction(biz: str | None) -> str:
    return IN if biz in ("IM", "DI") else OUT


def matches(cargo_group: str, biz: str | None) -> bool:
    d = direction_of(cargo_group)
    return d == BOTH or d == vessel_direction(biz)


def tank_group(cargo_group: str, product_class: str) -> str:
    if product_class == "CR":
        return "원유"
    d = direction_of(cargo_group)
    if d == IN:
        return "반입 원료"
    if d == BOTH:
        return "양방향"
    return f"{CLASS_LABEL.get(product_class, product_class)} 반출"
