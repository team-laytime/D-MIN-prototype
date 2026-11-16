package com.dmin.laytime;

import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;

/** 시각은 2026-01-01 00:00(KST)부터 센 '분' 정수다. Python 엔진(pptcalc.parse·iso)과 같은 기준점을 쓴다. */
public final class Times {

    public static final LocalDateTime EPOCH = LocalDateTime.of(2026, 1, 1, 0, 0);
    public static final long DAY = 1440;
    private static final DateTimeFormatter ISO_MIN = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm");
    private static final DateTimeFormatter SHORT = DateTimeFormatter.ofPattern("MM/dd HH:mm");

    private Times() {}

    /** "2026-11-10T09:00" (KST 현지 시각) → 분. 시간대(+09:00 등)가 붙은 값은 받지 않는다. */
    public static long parse(String text) {
        if (text == null || text.isBlank()) {
            throw new IllegalArgumentException("시각이 비어 있음");
        }
        String s = text.strip().replace(' ', 'T');
        try {
            LocalDateTime t = LocalDateTime.parse(s);
            return Math.floorDiv(Duration.between(EPOCH, t).toSeconds(), 60);
        } catch (DateTimeParseException e) {
            throw new IllegalArgumentException("시각 형식이 아님: '" + text + "' (KST 'YYYY-MM-DDTHH:MM')");
        }
    }

    public static Long parseOrNull(String text) {
        return text == null || text.isBlank() ? null : parse(text);
    }

    public static String iso(long minutes) {
        return EPOCH.plusMinutes(minutes).format(ISO_MIN);
    }

    public static String fmt(long minutes) {
        return EPOCH.plusMinutes(minutes).format(SHORT);
    }

    public static LocalDateTime local(long minutes) {
        return EPOCH.plusMinutes(minutes);
    }

    public static long day0(long t) {
        return t - Math.floorMod(t, DAY);
    }

    /** "08:00" → 480 */
    public static long hm(String text) {
        String[] p = text.split(":");
        return Long.parseLong(p[0]) * 60 + Long.parseLong(p[1]);
    }

    /** 시간(h) → 분. Python round(float(h) * 60)과 같게 짝수 반올림을 쓴다. */
    public static long mins(double hours) {
        return (long) Math.rint(hours * 60);
    }
}
