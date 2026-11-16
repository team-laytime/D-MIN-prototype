package com.dmin.common.money;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * USD 센트 금액. JSON에서는 정수 하나로 나간다. 금액은 이 타입으로만 내보내서 달러와 센트가 섞이지 않게 한다.
 * 계산 중간값은 계산 코드 안에서만 정확한 값으로 다루고, Money로는 한 번만 반올림해 확정한다.
 */
public record Money(@JsonValue long cents) {

    @JsonCreator(mode = JsonCreator.Mode.DELEGATING)
    public Money {}
}
