package com.dmin.cases;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.dmin.common.error.DminException;
import com.dmin.common.error.ErrorCode;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

/** PostgreSQL JSONB는 NUL(U+0000)을 저장하지 못한다 → DB 오류(500)가 되기 전에 입력 오류(400)로 돌려준다. */
class CaseServiceNulTest {

    private final JsonMapper json = JsonMapper.builder().build();

    @Test
    void nulIsRejectedBeforeTheDatabase() {
        CaseService cases = new CaseService(null, json); // DB까지 가기 전에 막히므로 JdbcClient가 없어도 된다
        DminException e = assertThrows(DminException.class, () -> cases.importJson("{\"id\":\"A\\u0000\",\"arrivals\":[]}", null));
        assertEquals(ErrorCode.VALIDATION, e.errorCode());
        assertEquals("글자 NUL(\\u0000)은 받지 않음", e.getMessage());
    }

    @Test
    void nulIsFoundInValuesAndKeysAtAnyDepth() {
        assertTrue(CaseService.hasNul(json.readTree("{\"a\":[1,{\"b\":\"x\\u0000\"}]}")));
        assertTrue(CaseService.hasNul(json.readTree("{\"a\":[1,{\"b\\u0000\":2}]}")));
        assertFalse(CaseService.hasNul(json.readTree("{\"a\":[\"\\\\u0000\"],\"b\":null}"))); // 역슬래시 + u0000 글자는 NUL이 아니다
    }
}
