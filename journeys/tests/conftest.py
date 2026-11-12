"""테스트 경로: journeys/(계산 모듈)와 clock/(기존 엔진, 교차 검증용)을 import 경로에 넣는다."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (HERE.parent, HERE.parents[1] / "clock"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
