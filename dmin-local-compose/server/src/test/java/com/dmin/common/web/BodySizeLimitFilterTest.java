package com.dmin.common.web;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import jakarta.servlet.http.HttpServletRequest;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

/** /api 아래 쓰기 요청의 본문 한도(기본 10MB). 길이를 알면 읽기 전에 413, 모르면 읽다가 한도에서 끊는다. */
class BodySizeLimitFilterTest {

    private static final long TEN_MB = 10L * 1024 * 1024;

    /** Content-Length 없이(chunked) 들어온 본문. */
    private static MockHttpServletRequest chunked(String uri, byte[] body) {
        MockHttpServletRequest req = new MockHttpServletRequest("POST", uri) {
            @Override
            public int getContentLength() {
                return -1;
            }

            @Override
            public long getContentLengthLong() {
                return -1;
            }
        };
        req.setContent(body);
        return req;
    }

    @Test
    void contentLengthOverTheLimitIs413BeforeReading() throws Exception {
        MockHttpServletRequest req = new MockHttpServletRequest("POST", "/api/cases");
        req.setContent(new byte[(int) TEN_MB + 1]);
        MockHttpServletResponse res = new MockHttpServletResponse();
        MockFilterChain chain = new MockFilterChain();
        new BodySizeLimitFilter(TEN_MB).doFilter(req, res, chain);
        assertEquals(413, res.getStatus());
        assertTrue(res.getContentType().startsWith("application/problem+json"), res.getContentType());
        assertEquals("{\"type\":\"about:blank\",\"title\":\"Payload Too Large\",\"status\":413,\"detail\":\"요청 본문이 10MB를 넘음\","
                + "\"code\":\"ERR_PAYLOAD_TOO_LARGE\"}", res.getContentAsString(StandardCharsets.UTF_8));
        assertNull(chain.getRequest()); // 컨트롤러까지 가지 않는다
    }

    @Test
    void withinTheLimitPassesUnchanged() throws Exception {
        MockHttpServletRequest req = new MockHttpServletRequest("POST", "/api/cases");
        req.setContent(new byte[(int) TEN_MB]);
        MockFilterChain chain = new MockFilterChain();
        new BodySizeLimitFilter(TEN_MB).doFilter(req, new MockHttpServletResponse(), chain);
        assertSame(req, chain.getRequest());
    }

    @Test
    void readsPassButEveryWriteIsLimitedWhateverThePath() throws Exception {
        MockHttpServletRequest get = new MockHttpServletRequest("GET", "/api/cases");
        get.setContent(new byte[64]);
        MockFilterChain chain = new MockFilterChain();
        new BodySizeLimitFilter(16).doFilter(get, new MockHttpServletResponse(), chain);
        assertSame(get, chain.getRequest()); // 읽기 요청은 건드리지 않는다

        // 경로를 바꿔도(/api;x=1 · %61pi · /internal) Spring은 같은 컨트롤러로 보낼 수 있으니 쓰기 요청은 모두 한도를 받는다
        for (String path : new String[] {"/api/cases", "/api;x=1/cases", "/%61pi/cases", "/internal/collect/eta"}) {
            MockHttpServletRequest post = new MockHttpServletRequest("POST", path);
            post.setContent(new byte[64]);
            MockHttpServletResponse res = new MockHttpServletResponse();
            MockFilterChain c = new MockFilterChain();
            new BodySizeLimitFilter(16).doFilter(post, res, c);
            assertEquals(413, res.getStatus(), path);
            assertNull(c.getRequest(), path); // 컨트롤러까지 가지 않는다
        }
    }

    @Test
    void unknownLengthIsCountedWhileReading() throws Exception {
        MockFilterChain chain = new MockFilterChain();
        new BodySizeLimitFilter(16).doFilter(chunked("/api/runs", new byte[17]), new MockHttpServletResponse(), chain);
        HttpServletRequest seen = (HttpServletRequest) chain.getRequest();
        IOException e = assertThrows(IOException.class, () -> seen.getInputStream().readAllBytes());
        assertEquals(BodySizeLimitFilter.TooLargeException.class, e.getClass());
        assertEquals("요청 본문이 16바이트를 넘음", e.getMessage());

        MockFilterChain ok = new MockFilterChain();
        byte[] body = "{\"case_id\":1}".getBytes(StandardCharsets.UTF_8);
        new BodySizeLimitFilter(16).doFilter(chunked("/api/runs", body), new MockHttpServletResponse(), ok);
        HttpServletRequest small = (HttpServletRequest) ok.getRequest();
        assertArrayEquals(body, small.getInputStream().readAllBytes()); // 한도 안이면 그대로 읽힌다
    }
}
