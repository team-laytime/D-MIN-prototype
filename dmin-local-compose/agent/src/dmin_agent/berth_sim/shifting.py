"""부두별 Shifting 소요시간 (멘토링 장표 07p).

- Direction: 부두가 비어 있을 때 ETA 이후 접안까지 걸리는 시간
- Switching: 앞 선박 이안(ETU) 후 다음 선박 접안까지 걸리는 교대시간
"""

from datetime import timedelta

# 장표 표 그대로: 그룹명 -> (Switching, Direction) [hour]
SHIFTING_HOURS: dict[str, tuple[float, float]] = {
    "#1~2": (1.5, 1.0),
    "#3": (1.5, 1.0),
    "#4": (1.0, 1.0),
    "#5-5": (1.0, 1.0),  # 장표 표기 그대로. 5-1~5-5 전체에 적용하는 것으로 가정 (현업 확인 필요)
    "GAS1/2": (1.0, 1.0),
    "#6": (2.5, 1.5),
    "#7": (2.5, 1.5),
    "#8": (2.5, 1.5),
    "Buoy": (1.0, 1.5),
}


def normalize_berth(raw: str) -> str:
    """샘플 데이터의 부두 표기를 `부두별 제원` 시트 표기(1-1, 3, GAS1, BUOY2 …)로 통일한다.

    '#1-1' -> '1-1', '#6' -> '6', '#1 Gas' -> 'GAS1', '#2 Buoy' -> 'BUOY2'
    """
    s = raw.strip().lstrip("#").strip()
    parts = s.split()
    if len(parts) == 2 and parts[1].upper() in ("GAS", "BUOY"):
        return f"{parts[1].upper()}{parts[0]}"
    return s.upper()


def shifting_group(berth: str) -> str:
    """정규화된 부두명 -> Shifting 표의 행 이름."""
    if berth.startswith("GAS"):
        return "GAS1/2"
    if berth.startswith("BUOY"):
        return "Buoy"
    head = berth.split("-")[0]
    if head in ("1", "2"):
        return "#1~2"
    if head == "5":
        return "#5-5"
    group = f"#{head}"
    if group not in SHIFTING_HOURS:
        raise KeyError(f"Shifting 표에 없는 부두: {berth}")
    return group


def switching(berth: str) -> timedelta:
    return timedelta(hours=SHIFTING_HOURS[shifting_group(berth)][0])


def direction(berth: str) -> timedelta:
    return timedelta(hours=SHIFTING_HOURS[shifting_group(berth)][1])
