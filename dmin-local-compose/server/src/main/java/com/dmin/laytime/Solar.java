package com.dmin.laytime;

/**
 * 그날의 일출·일몰(분). NOAA 근사식 — Python 엔진 pptcalc.solar와 같은 식·같은 계산 순서다.
 * 운영에서는 요청의 sun에 공공데이터(한국천문연구원 출몰시각)를 넣는다. 그러면 이 식은 쓰이지 않는다.
 */
final class Solar {

    private Solar() {}

    static long[] riseSet(long dayStart, double lat, double lon, double tzHours) {
        int n = Times.local(dayStart).getDayOfYear();
        double g = 2 * Math.PI / 365 * (n - 1);
        double eqtime = 229.18
                * (0.000075
                        + 0.001868 * StrictMath.cos(g)
                        - 0.032077 * StrictMath.sin(g)
                        - 0.014615 * StrictMath.cos(2 * g)
                        - 0.040849 * StrictMath.sin(2 * g));
        double decl = 0.006918
                - 0.399912 * StrictMath.cos(g)
                + 0.070257 * StrictMath.sin(g)
                - 0.006758 * StrictMath.cos(2 * g)
                + 0.000907 * StrictMath.sin(2 * g)
                - 0.002697 * StrictMath.cos(3 * g)
                + 0.00148 * StrictMath.sin(3 * g);
        double la = Math.toRadians(lat);
        double ha = Math.toDegrees(StrictMath.acos(StrictMath.cos(Math.toRadians(90.833))
                        / (StrictMath.cos(la) * StrictMath.cos(decl))
                - StrictMath.tan(la) * StrictMath.tan(decl)));
        double rise = 720 - 4 * (lon + ha) - eqtime + tzHours * 60;
        double sset = 720 - 4 * (lon - ha) - eqtime + tzHours * 60;
        return new long[] {dayStart + (long) Math.rint(rise), dayStart + (long) Math.rint(sset)};
    }
}
