"""실행 스크립트에서 샘플 선박에 FIX/제원을 덮어쓰는 도우미."""

from dataclasses import replace
from datetime import datetime

from .models import Vessel


def _update(sequences: dict[str, list[Vessel]], vessel_id: str, **changes) -> None:
    seq = sequences[vessel_id.split("#")[0]]
    idx = next(i for i, v in enumerate(seq) if v.vessel_id == vessel_id)
    seq[idx] = replace(seq[idx], **changes)


def set_fix(sequences: dict[str, list[Vessel]], vessel_id: str, etb: datetime) -> None:
    _update(sequences, vessel_id, is_fix=True, fixed_etb=etb)


def set_spec(sequences: dict[str, list[Vessel]], vessel_id: str, grt: float, draft: float) -> None:
    _update(sequences, vessel_id, grt=grt, draft=draft)


def set_cargo(sequences: dict[str, list[Vessel]], vessel_id: str, cargo_group: str) -> None:
    _update(sequences, vessel_id, cargo_group=cargo_group)
