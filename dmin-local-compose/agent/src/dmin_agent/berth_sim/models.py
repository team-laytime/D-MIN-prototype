from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Vessel:
    vessel_id: str
    berth: str  # 정규화된 부두명 (shifting.normalize_berth)
    eta: datetime
    # 접안(ETB) ~ 이안(ETU) 부두 점유시간. 기상 하역 중단이 있으면 ETB에 따라 달라지므로 stay_for(etb)로 읽는다.
    stay: timedelta
    is_fix: bool = False
    fixed_etb: datetime | None = None  # is_fix=True 일 때 필수
    biz: str | None = None  # EX(수출)/IM(수입)/DO(내수 판매)/DI(내수 매입)
    grt: float | None = None  # ② 야간 도선
    draft: float | None = None  # ② 야간 도선 (단일 Draft 값)
    cargo_group: str | None = None  # ③ 동일 화물 그룹 (Sample data `부두 별 접안 가능 제품 그룹`의 제품 그룹: DSL, R-G …)
    # ETB → 점유시간. 기상 하역 중단 구간이 있으면 작업이 멈춘 만큼 길어진다 (scenario.build_sequences에서 설정)
    stay_at: Callable[[datetime], timedelta] | None = field(default=None, compare=False, repr=False)

    def stay_for(self, etb: datetime) -> timedelta:
        return self.stay_at(etb) if self.stay_at is not None else self.stay

    def __post_init__(self) -> None:
        if self.is_fix and self.fixed_etb is None:
            raise ValueError(f"{self.vessel_id}: FIX 선박은 fixed_etb가 필요합니다.")

    @property
    def is_import(self) -> bool:
        return self.biz == "IM"
