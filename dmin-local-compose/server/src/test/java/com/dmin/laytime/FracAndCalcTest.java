package com.dmin.laytime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class FracAndCalcTest {

    @Test
    void fractionsMatchPythonFraction() {
        assertEquals(Frac.of(1, 2), Frac.parse("1/2"));
        assertEquals(Frac.of(1, 2), Frac.parse("0.5"));
        assertEquals(Frac.of(1, 2), Frac.fromDouble(0.5));
        assertEquals(Frac.of(1, 3), Frac.fromDouble(1.0 / 3)); // limit_denominator(1000)
        assertEquals(Frac.of(5, 2), Frac.of(2).add(Frac.HALF));
    }

    @Test
    void centsAreRoundedOnceHalfUp() {
        // 체선시간 1분 × 하루 1센트 ÷ 1440 → 0.0007센트 → 0 · 720분 × 1센트 ÷ 1440 = 0.5 → 1
        assertEquals(0, Frac.of(1).mul(1).div(1440).floorHalfUp());
        assertEquals(1, Frac.of(720).mul(1).div(1440).floorHalfUp());
    }

    @Test
    void timesUseTheEngineEpoch() {
        long t = Times.parse("2026-11-10T09:00");
        assertEquals("2026-11-10T09:00", Times.iso(t));
        assertEquals(Times.parse("2026-11-10T00:00"), Times.day0(t));
        assertEquals(90, Times.mins(1.5));
    }

    @Test
    void bundledRulesLoad() {
        Rules rules = Rules.bundled();
        assertEquals("ulsan-clx/ppt-v1", rules.version());
        assertEquals(24, rules.berthOrder().size());
        assertTrue(rules.berths().containsKey("#8"));
        assertFalse(rules.sha256().isBlank());
    }
}
