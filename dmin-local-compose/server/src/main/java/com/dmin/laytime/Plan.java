package com.dmin.laytime;

/**
 * 작업계획 하나 = (입항 건, 부두, 접안 시각) + PPT 09~11쪽 식으로 따라 나온 시각·금액.
 * 시각은 분, 금액은 센트. 정박종료·체선시간은 ½분이 생길 수 있어 분수로 둔다.
 */
public record Plan(
        String aid,
        String berth,
        long s,
        long a,
        long c,
        long h,
        long u,
        long layStart,
        String layRule,
        String layText,
        Frac allowed,
        Frac layEnd,
        Frac dtRaw,
        Frac wx,
        Frac ded,
        Frac dt,
        long cents,
        boolean fixed) {}
