package com.dmin.laytime;

import java.math.BigDecimal;
import java.math.BigInteger;

/**
 * 정확한 분수(분자/분모). Python 엔진의 {@code fractions.Fraction}과 같은 값을 내려고 쓴다.
 * 정박시간 ½·기상 공제 ½ 때문에 분 단위 시간도 0.5분이 생기고, 금액은 마지막에 한 번만 반올림한다(정의서 4.2).
 */
public record Frac(long num, long den) implements Comparable<Frac> {

    public static final Frac ZERO = new Frac(0, 1);
    public static final Frac ONE = new Frac(1, 1);
    public static final Frac HALF = new Frac(1, 2);

    public Frac {
        if (den == 0) {
            throw new ArithmeticException("분모가 0");
        }
        if (den < 0) {
            num = Math.negateExact(num);
            den = Math.negateExact(den);
        }
        long g = gcd(Math.abs(num), den);
        if (g > 1) {
            num /= g;
            den /= g;
        }
    }

    public static Frac of(long n) {
        return new Frac(n, 1);
    }

    public static Frac of(long n, long d) {
        return new Frac(n, d);
    }

    /** "1/2" 또는 "0.5" 꼴 글자 → 분수 (Python Fraction(str)과 같다). */
    public static Frac parse(String text) {
        String s = text.strip();
        int slash = s.indexOf('/');
        if (slash >= 0) {
            return new Frac(Long.parseLong(s.substring(0, slash).strip()), Long.parseLong(s.substring(slash + 1).strip()));
        }
        BigDecimal d = new BigDecimal(s);
        return new Frac(d.unscaledValue().longValueExact(), BigInteger.TEN.pow(Math.max(d.scale(), 0)).longValueExact())
                .mul(d.scale() < 0 ? BigInteger.TEN.pow(-d.scale()).longValueExact() : 1);
    }

    /** 숫자 → 분모 1000 이하의 가장 가까운 분수 (Python Fraction(x).limit_denominator(1000)과 같다). */
    public static Frac fromDouble(double x) {
        BigDecimal exact = new BigDecimal(x);
        BigInteger n = exact.unscaledValue();
        BigInteger d = BigInteger.ONE;
        if (exact.scale() > 0) {
            d = BigInteger.TEN.pow(exact.scale());
        } else if (exact.scale() < 0) {
            n = n.multiply(BigInteger.TEN.pow(-exact.scale()));
        }
        BigInteger g = n.gcd(d);
        if (g.signum() != 0) {
            n = n.divide(g);
            d = d.divide(g);
        }
        BigInteger max = BigInteger.valueOf(1000);
        if (d.compareTo(max) <= 0) {
            return new Frac(n.longValueExact(), d.longValueExact());
        }
        // CPython Fraction.limit_denominator 알고리즘 그대로
        BigInteger p0 = BigInteger.ZERO, q0 = BigInteger.ONE, p1 = BigInteger.ONE, q1 = BigInteger.ZERO;
        BigInteger nn = n, dd = d;
        while (true) {
            BigInteger a = floorDiv(nn, dd);
            BigInteger q2 = q0.add(a.multiply(q1));
            if (q2.compareTo(max) > 0) {
                break;
            }
            BigInteger np0 = p1, nq0 = q1, np1 = p0.add(a.multiply(p1)), nq1 = q2;
            p0 = np0;
            q0 = nq0;
            p1 = np1;
            q1 = nq1;
            BigInteger nd = nn.subtract(a.multiply(dd));
            nn = dd;
            dd = nd;
            if (dd.signum() == 0) {
                break;
            }
        }
        BigInteger k = floorDiv(max.subtract(q0), q1);
        // bound1 = (p0 + k*p1)/(q0 + k*q1), bound2 = p1/q1
        BigInteger b1n = p0.add(k.multiply(p1)), b1d = q0.add(k.multiply(q1));
        BigInteger b2n = p1, b2d = q1;
        // |bound2 - x| <= |bound1 - x| 이면 bound2
        BigInteger e2 = b2n.multiply(d).subtract(n.multiply(b2d)).abs().multiply(b1d);
        BigInteger e1 = b1n.multiply(d).subtract(n.multiply(b1d)).abs().multiply(b2d);
        return e2.compareTo(e1) <= 0
                ? new Frac(b2n.longValueExact(), b2d.longValueExact())
                : new Frac(b1n.longValueExact(), b1d.longValueExact());
    }

    private static BigInteger floorDiv(BigInteger a, BigInteger b) {
        BigInteger[] qr = a.divideAndRemainder(b);
        return (qr[1].signum() != 0 && (qr[1].signum() != b.signum())) ? qr[0].subtract(BigInteger.ONE) : qr[0];
    }

    public Frac add(Frac o) {
        return new Frac(
                Math.addExact(Math.multiplyExact(num, o.den), Math.multiplyExact(o.num, den)), Math.multiplyExact(den, o.den));
    }

    public Frac add(long n) {
        return add(of(n));
    }

    public Frac sub(Frac o) {
        return add(new Frac(Math.negateExact(o.num), o.den));
    }

    public Frac mul(Frac o) {
        return new Frac(Math.multiplyExact(num, o.num), Math.multiplyExact(den, o.den));
    }

    public Frac mul(long n) {
        return new Frac(Math.multiplyExact(num, n), den);
    }

    public Frac div(long n) {
        return new Frac(num, Math.multiplyExact(den, n));
    }

    public int signum() {
        return Long.signum(num);
    }

    public static Frac max(Frac a, Frac b) {
        return a.compareTo(b) >= 0 ? a : b;
    }

    public static Frac min(Frac a, Frac b) {
        return a.compareTo(b) <= 0 ? a : b;
    }

    /** floor(x) — 시각을 분 정수로 돌릴 때 (Python int(Fraction)은 0 쪽으로 자르지만 시각은 양수라 같다). */
    public long floor() {
        return Math.floorDiv(num, den);
    }

    /** floor(x + ½) — 금액을 센트로 확정할 때 한 번만 쓴다 (엔진의 P19와 같다). */
    public long floorHalfUp() {
        return Math.floorDiv(Math.addExact(Math.multiplyExact(2, num), den), Math.multiplyExact(2, den));
    }

    public double toDouble() {
        return (double) num / (double) den;
    }

    @Override
    public int compareTo(Frac o) {
        return Long.compare(Math.multiplyExact(num, o.den), Math.multiplyExact(o.num, den));
    }

    private static long gcd(long a, long b) {
        while (b != 0) {
            long t = a % b;
            a = b;
            b = t;
        }
        return a == 0 ? 1 : a;
    }

    @Override
    public String toString() {
        return den == 1 ? Long.toString(num) : num + "/" + den;
    }
}
