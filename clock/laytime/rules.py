"""룰 레지스트리. 계산서의 모든 줄·구간·쟁점은 여기 등록된 rule_id만 근거로 쓴다(오타는 즉시 KeyError).

source 열 = docs/domain/05-charter-party-clauses.md 의 위치(§2 서식 조항, §2-1 판례·엔진 룰, §3 Shellvoy·BPVOY, §5 터미널 룰).
prototype/data/rules.json 과 같은 ID를 쓴다.

status 값은 05 §6·prototype/data/rules.json 과 같다(confirmed는 아직 없음).
verify = 서식 원문·판례 대조 전 [확인 필요] / public = 공개자료로 확인 [사실] /
assumed = 임의로 둔 값 [가정] / disputed = 해석이 갈림 [쟁점]
"""
from __future__ import annotations

from dataclasses import dataclass

RULES_VERSION = "2026-11-02-draft"

STATUS_TAG = {"verify": "[확인 필요]", "public": "[사실]", "assumed": "[가정]", "disputed": "[쟁점]"}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    source: str
    status: str

    @property
    def tag(self) -> str:
        return STATUS_TAG[self.status]


_RULES = (
    Rule("ASB-06-NOR-START", "레이타임 개시 = min(NOR 수령 + 통지시간, 접안·계류 완료)", "05 §2 cl.6", "verify"),
    Rule("ASB-06-BERTH-DELAY-EXC", "NOR 후 용선주 통제 밖 사유로 접안이 늦어진 시간은 used laytime 불산입(용선주 주장 근거)",
         "05 §2 cl.6", "disputed"),
    Rule("ASB-07-HOURS", "Part I의 running hours를 레이타임으로 허용", "05 §2 cl.7", "verify"),
    Rule("ASB-07-SHIFTING-EXCL", "묘박지→선석 이동 시간은 used laytime 불산입", "05 §2 cl.7", "verify"),
    Rule("ASB-07-VESSEL-FAULT", "선박 상태·고장·설비 부족으로 인한 지연 불산입", "05 §2 cl.7", "verify"),
    Rule("ASB-08-RATE-PRORATA", "체선료 = 허용 초과 시간 × Part I 요율(USD/일), 시간 비례", "05 §2 cl.8", "verify"),
    Rule("ASB-08-HALF-RATE", "화재·폭발·폭풍·파업·용선주 측 플랜트 고장으로 생긴 체선은 반액", "05 §2 cl.8", "verify"),
    Rule("ASB-09-REACHABLE", "용선주는 도착 즉시 접근 가능한 선석을 제공할 의무 — 묘박 대기 시간은 산입", "05 §2 cl.9", "verify"),
    Rule("ASB-11-END-HOSES", "레이타임·체선은 호스 분리 시 종료", "05 §2 cl.11", "verify"),
    Rule("RIDER-PUMPING", "펌핑 보증(전량 24h 내 양하 또는 매니폴드 100 psi) 미달 시 초과 시간은 선주 부담 — 육상 제한이 없을 때만",
         "05 §2 cl.10·§3, 04 예제 4", "assumed"),
    Rule("SV6-DOCS-WAIT", "호스 분리 후 서류 대기가 일정 시간(예 3h)을 넘으면 초과분 산입 (Shellvoy 6)", "05 §3", "verify"),
    Rule("BPV4-DOCS-WAIT", "호스 분리 후 서류 대기가 일정 시간(예 3h)을 넘으면 초과분 산입 (BPVOY4)", "05 §3", "verify"),
    Rule("ULS-SBM-NIGHT", "SK Buoy(SBM)는 야간 계류 불가, 이안은 주야 가능", "05 §5 (SEAGATE Entry Guide)", "public"),
    Rule("ULS-SK38-DAYTIME", "SK3~8: 공선 30,000GT 이상·적재 25,000GT 이상 선박은 접안 주간만", "05 §5 (SEAGATE Entry Guide)", "public"),
    Rule("ULS-SK12-DAYTIME", "SK1~2: 아스팔트·윤활유·유황 선적선 외 주간 접·이안", "05 §5 (SEAGATE Entry Guide)", "public"),
    Rule("ULS-DAYTIME-DEF", "'주간' = 07:00~17:30 (접안 완료 시각이 이 창 안이어야 함)", "05 §5", "assumed"),
    Rule("LAW-ONCE-ON-DEM", "일단 체선이면 계속 체선 — 'demurrage'를 명시하지 않은 레이타임 예외는 체선 중 미적용",
         "05 §2-1 (The Spalmatori, The Nikmary)", "disputed"),
    Rule("LAW-NOR-ARRIVAL", "도착(관습 묘박지 투묘) 전에 낸 NOR은 무효 — 재제출 전까지 효력 없음",
         "05 §2-1 (The Mexico I, The Johanna Oldendorff)", "verify"),
    Rule("LAW-NOR-WAIVER", "무효 NOR 후 용선주가 이의 없이 하역을 시작하면 하역 개시부터 레이타임 (The Happy Day)",
         "05 §2-1 (The Happy Day)", "verify"),
    Rule("ENG-LOW-MARGIN", "체선이 없어도 레이타임 여유가 2시간 미만이면 경고", "05 §2-1 (04 예제 1 교훈)", "assumed"),
)

REGISTRY = {r.rule_id: r for r in _RULES}

# 체선이 없어도 경고하는 여유 기준 (ENG-LOW-MARGIN) [가정]
LOW_MARGIN_HOURS = 2
# 서류 대기 쟁점을 올리는 기준 = 서식별 유예 시간의 예시값 (05 §3 "예: 3시간") [가정]
DOCS_WAIT_GRACE_HOURS = 3


def rule(rule_id: str) -> Rule:
    if rule_id not in REGISTRY:
        raise KeyError(f"등록되지 않은 rule_id: {rule_id}")
    return REGISTRY[rule_id]


def check(*rule_ids: str) -> tuple[str, ...]:
    """rule_id 묶음을 검증해 그대로 돌려준다. 순서 유지, 중복 제거."""
    out: list[str] = []
    for r in rule_ids:
        rule(r)
        if r not in out:
            out.append(r)
    return tuple(out)
