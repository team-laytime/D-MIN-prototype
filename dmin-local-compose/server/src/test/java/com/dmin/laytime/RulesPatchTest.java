package com.dmin.laytime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.Map;
import org.junit.jupiter.api.Test;

/** rule_patch는 규칙 표에 이미 있는 값만 바꾼다. 오타로 새 키가 생겨 아무것도 안 바뀐 채 계산되면 안 된다. */
class RulesPatchTest {

    @Test
    void knownKeyIsChanged() {
        assertEquals("USED", Rules.bundled().wxBasis);
        assertEquals("WAIT", Rules.bundled(Map.of("demurrage.weather_basis", "WAIT")).wxBasis);
        Rules r = Rules.bundled(Map.of("berths.0.max_dwt", 9000, "berths.0.min_pbl", 50)); // min_pbl은 표에 null로 있다 = 있는 키
        assertEquals(9000.0, r.berths().get("#1-1").maxDwt());
        assertEquals(50.0, r.berths().get("#1-1").minPbl());
        assertNull(Rules.bundled().berths().get("#1-1").minPbl());
    }

    @Test
    void unknownKeyIsRejected() {
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> Rules.bundled(Map.of("demurrage.weather_basiss", "WAIT")));
        assertEquals("rule_patch 경로 없음: demurrage.weather_basiss", e.getMessage());
        assertThrows(IllegalArgumentException.class, () -> Rules.bundled(Map.of("demurage.weather_basis", "WAIT"))); // 중간 키 오타
        assertThrows(IllegalArgumentException.class, () -> Rules.bundled(Map.of("berths.24.max_dwt", 1))); // 부두는 24개(0~23)
        assertThrows(IllegalArgumentException.class, () -> Rules.bundled(Map.of("berths.-1.max_dwt", 1)));
        assertThrows(IllegalArgumentException.class, () -> Rules.bundled(Map.of("berths.first.max_dwt", 1)));
        assertThrows(IllegalArgumentException.class, () -> Rules.bundled(Map.of("version.x", 1))); // 값 아래로는 못 내려간다
    }
}
