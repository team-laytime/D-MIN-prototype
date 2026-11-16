package com.dmin.common.web;

import com.dmin.common.error.ErrorCode;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ReadListener;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletInputStream;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import jakarta.servlet.http.HttpServletResponse;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 모든 POST·PUT·PATCH 요청 본문의 크기 한도 (dmin.web.max-body-bytes, 기본 10MB).
 * Content-Length가 한도를 넘으면 본문을 읽기 전에 413으로 끊는다. 길이를 모르는 본문(chunked)은 읽으면서 세다가
 * 한도를 넘는 순간 IOException(TooLargeException)을 던진다 → ApiExceptionHandler가 413으로 바꾼다.
 * 파일 업로드(multipart)는 컨테이너가 직접 읽으므로 spring.servlet.multipart 한도가 함께 지킨다.
 */
@Component
public class BodySizeLimitFilter extends OncePerRequestFilter {

    /** 길이를 모르는 본문이 한도를 넘었을 때 읽는 중에 던진다. 메시지는 응답의 detail이 된다. */
    public static class TooLargeException extends IOException {
        TooLargeException(String message) {
            super(message);
        }
    }

    private final long limit;
    private final String detail;
    private final String body;

    public BodySizeLimitFilter(@Value("${dmin.web.max-body-bytes:10485760}") long limit) {
        this.limit = limit;
        this.detail = "요청 본문이 " + size(limit) + "를 넘음";
        this.body = "{\"type\":\"about:blank\",\"title\":\"Payload Too Large\",\"status\":413,\"detail\":\"" + detail
                + "\",\"code\":\"" + ErrorCode.PAYLOAD_TOO_LARGE.code() + "\"}";
    }

    /** 10485760 → "10MB". MB·KB로 나누어떨어지지 않으면 바이트로 적는다. */
    static String size(long bytes) {
        if (bytes > 0 && bytes % (1024 * 1024) == 0) {
            return bytes / (1024 * 1024) + "MB";
        }
        if (bytes > 0 && bytes % 1024 == 0) {
            return bytes / 1024 + "KB";
        }
        return bytes + "바이트";
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String m = request.getMethod();
        boolean writes = "POST".equals(m) || "PUT".equals(m) || "PATCH".equals(m);
        // 경로로 거르지 않는다: /api;x=1/cases · /%61pi/cases처럼 경로를 바꿔도 Spring은 같은 컨트롤러로 보내기 때문이다.
        // 쓰기 요청은 모두 같은 한도를 받는다(본문이 없는 /internal 수집 요청에는 영향이 없다).
        return !writes;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        long length = request.getContentLengthLong();
        if (length > limit) {
            response.setStatus(ErrorCode.PAYLOAD_TOO_LARGE.status().value());
            response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
            response.setCharacterEncoding(StandardCharsets.UTF_8.name());
            response.getWriter().write(body);
            return;
        }
        // 길이를 아는 본문은 컨테이너가 Content-Length만큼만 읽는다. 모르는 본문만 세면서 읽게 감싼다.
        chain.doFilter(length < 0 ? new Limited(request, limit, detail) : request, response);
    }

    private static final class Limited extends HttpServletRequestWrapper {

        private final long limit;
        private final String detail;
        private ServletInputStream in;
        private BufferedReader reader;

        Limited(HttpServletRequest request, long limit, String detail) {
            super(request);
            this.limit = limit;
            this.detail = detail;
        }

        @Override
        public ServletInputStream getInputStream() throws IOException {
            if (in == null) {
                in = new Counting(super.getInputStream(), limit, detail);
            }
            return in;
        }

        @Override
        public BufferedReader getReader() throws IOException {
            if (reader == null) { // 원래 getReader()는 세지 않고 읽으므로 센 스트림 위에 새로 만든다
                String enc = getCharacterEncoding();
                Charset cs = enc == null ? StandardCharsets.ISO_8859_1 : Charset.forName(enc);
                reader = new BufferedReader(new InputStreamReader(getInputStream(), cs));
            }
            return reader;
        }
    }

    private static final class Counting extends ServletInputStream {

        private final ServletInputStream in;
        private final long limit;
        private final String detail;
        private long count;

        Counting(ServletInputStream in, long limit, String detail) {
            this.in = in;
            this.limit = limit;
            this.detail = detail;
        }

        @Override
        public int read() throws IOException {
            int b = in.read();
            if (b >= 0) {
                add(1);
            }
            return b;
        }

        @Override
        public int read(byte[] buf, int off, int len) throws IOException {
            int n = in.read(buf, off, len);
            if (n > 0) {
                add(n);
            }
            return n;
        }

        private void add(int n) throws IOException {
            count += n;
            if (count > limit) {
                throw new TooLargeException(detail);
            }
        }

        @Override
        public int available() throws IOException {
            return in.available();
        }

        @Override
        public void close() throws IOException {
            in.close();
        }

        @Override
        public boolean isFinished() {
            return in.isFinished();
        }

        @Override
        public boolean isReady() {
            return in.isReady();
        }

        @Override
        public void setReadListener(ReadListener listener) {
            in.setReadListener(listener);
        }
    }
}
