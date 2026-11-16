"""Day Light 적용?

  * Daylight 적용   - 원유선, 석유제품선
  * Daylight 미적용 - 특수제품선, 윤활유제품선, 화학제품선
선종 이름은 Sample data `부두 별 접안 가능 제품 그룹` 시트의 '참고 - 제품 분류' 표기를 따른다.
"""

DAYLIGHT_APPLIED = frozenset({"원유선", "석유제품선"})
DAYLIGHT_NOT_APPLIED = frozenset({"특수제품선", "윤활유제품선", "화학제품선"})


def is_daylight(vessel_type: str) -> bool:
    if vessel_type in DAYLIGHT_APPLIED:
        return True
    if vessel_type in DAYLIGHT_NOT_APPLIED:
        return False
    raise ValueError(f"Daylight 적용 여부를 알 수 없는 선종: {vessel_type}")
