"""규칙 테이블 로더 (NFR-04 규칙 분리·버전 관리, NFR-05 규칙 ID 추적).

계산에 쓰는 값은 모두 data/ 아래 JSON 표에서 읽는다. 코드에는 '어떻게 계산하나'만 있고
'몇 시간·몇 톤·몇 퍼센트'는 없다. 표를 바꾸면 코드 수정 없이 결과와 근거의 규칙 이름이 바뀐다.

버전: 표 다섯 개의 내용을 정렬한 JSON의 SHA-256 앞 12자리. 실행 기록에 남겨 같은 규칙으로 다시 돌릴 수 있게 한다.
patch: {"contract.weather_deduction.ratio": 0} 처럼 점 경로로 값을 바꿔 '만약' 계산을 한다(실행 기록에 patch도 남긴다).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Optional

from ..domain.model import Berth
from ..domain.timeutil import hours_to_min

DATA_DIR = Path(os.environ.get("DEMURRAGE_DATA_DIR") or Path(__file__).resolve().parents[3] / "data")

DEFAULT_FILES = {
    "terminal": "master/terminal_ulsan_clx.v1.json",
    "cargo": "master/cargo_groups.v1.json",
    "contract": "rules/contract_rules.v1.json",
    "registry": "rules/rule_registry.v1.json",
    "phrases": "rules/risk_phrases.v1.json",
}


def canonical_hash(obj) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def _deep_set(doc: dict, dotted: str, value):
    parts = dotted.split(".")
    cur = doc
    for p in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[int(p)]
        else:
            cur = cur.setdefault(p, {})
    last = parts[-1]
    if isinstance(cur, list):
        cur[int(last)] = value
    else:
        cur[last] = value


@dataclass
class RuleSet:
    docs: dict
    version: str
    file_versions: dict
    patch: dict
    berths: dict = field(default_factory=dict)
    berth_order: list = field(default_factory=list)
    combos: list = field(default_factory=list)          # [frozenset(berth_ids)]
    pairs: list = field(default_factory=list)           # [(frozenset, exempt_grt)]
    release_min: int = 120
    night: dict = field(default_factory=dict)
    wind_limits: dict = field(default_factory=dict)
    daylight_types: frozenset = frozenset()
    notice_min: int = 360
    early_start_min: int = 360
    daylight: dict = field(default_factory=dict)
    contract_types: dict = field(default_factory=dict)
    weather_ratio: Fraction = Fraction(1, 2)
    work_start_delay_min: int = 60
    etu_after_work_min: int = 120
    cargo_map: dict = field(default_factory=dict)
    cargo_names: dict = field(default_factory=dict)
    rule_index: dict = field(default_factory=dict)
    phrases: dict = field(default_factory=dict)
    location: dict = field(default_factory=dict)

    def rule_name(self, rule_id: str) -> str:
        r = self.rule_index.get(rule_id)
        return f"{rule_id} {r['name']}" if r else rule_id

    def rule(self, rule_id: str) -> dict:
        return self.rule_index.get(rule_id, {"id": rule_id, "name": rule_id, "text": "", "status": "미등록"})

    def summary(self) -> dict:
        return {"version": self.version, "files": self.file_versions, "patch": self.patch}


def load_rules(files: Optional[dict] = None, patch: Optional[dict] = None, data_dir: Optional[Path] = None) -> RuleSet:
    base = Path(data_dir) if data_dir else DATA_DIR
    names = dict(DEFAULT_FILES)
    if files:
        names.update(files)
    docs = {}
    for key, rel in names.items():
        p = Path(rel)
        if not p.is_absolute():
            p = base / rel
        docs[key] = json.loads(p.read_text(encoding="utf-8"))
    patch = dict(patch or {})
    for dotted, value in patch.items():
        head, _, rest = dotted.partition(".")
        if head not in docs or not rest:
            raise KeyError(f"patch 경로 오류: {dotted} (terminal/cargo/contract/registry/phrases 중 하나로 시작)")
        docs[head] = copy.deepcopy(docs[head])
        _deep_set(docs[head], rest, value)

    file_versions = {k: f"{docs[k].get('version', k)}#{canonical_hash(docs[k])}" for k in docs}
    version = canonical_hash({k: docs[k] for k in sorted(docs)})
    rs = RuleSet(docs=docs, version=version, file_versions=file_versions, patch=patch)

    term = docs["terminal"]
    shift = term["shifting_hours"]
    for i, b in enumerate(term["berths"]):
        sh = shift[b["shift_group"]]
        rs.berths[b["id"]] = Berth(
            id=b["id"], shift_group=b["shift_group"], type=b["type"], max_dwt=int(b["max_dwt"]),
            min_loa=float(b["min_loa"]), max_loa=float(b["max_loa"]), min_pbl=float(b["min_pbl"]),
            max_draft=float(b["max_draft"]), cargo_groups=tuple(b["cargo_groups"]),
            direction=hours_to_min(sh["direction"]), switching=hours_to_min(sh["switching"]),
            tide_draft_threshold=b.get("tide_draft_threshold"), order=i,
        )
        rs.berth_order.append(b["id"])
    rs.combos = [frozenset(c) for c in term["same_cargo_group_combos"]["combos"]]
    rs.pairs = [(frozenset(p["berths"]), int(p.get("exempt_if_all_grt_le", 0))) for p in term["simultaneous_berthing_pairs"]["pairs"]]
    rs.release_min = hours_to_min(term.get("overlap_release_before_etu_h", 2))
    rs.night = term["night_pilotage"]
    rs.wind_limits = term["weather_limits"]["berthing_wind_ms"]
    rs.daylight_types = frozenset(term["daylight_vessel_types"]["apply"])
    rs.location = term.get("location", {})

    con = docs["contract"]
    ls = con["laytime_start"]
    rs.notice_min = hours_to_min(ls["notice_hours"])
    rs.early_start_min = hours_to_min(ls["early_arrival_start_hour"])
    rs.daylight = ls["daylight"]
    rs.contract_types = con["contract_types"]
    rs.weather_ratio = Fraction(str(con["weather_deduction"]["ratio"]))
    rs.work_start_delay_min = hours_to_min(con["work_times"]["work_start_delay_h"])
    rs.etu_after_work_min = hours_to_min(con["work_times"]["etu_after_work_end_h"])

    rs.cargo_map = dict(docs["cargo"]["map"])
    rs.cargo_names = dict(docs["cargo"].get("group_names", {}))
    rs.rule_index = {r["id"]: r for r in docs["registry"]["rules"]}
    rs.phrases = docs["phrases"]
    return rs
