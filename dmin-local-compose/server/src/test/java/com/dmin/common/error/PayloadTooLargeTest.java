package com.dmin.common.error;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.dmin.common.web.BodySizeLimitFilter;
import jakarta.servlet.Filter;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/** 길이를 모르는 본문(chunked)이 한도를 넘으면 읽는 도중에 끊기고, 400(읽기 오류)이 아니라 413 + ERR_PAYLOAD_TOO_LARGE가 된다. */
class PayloadTooLargeTest {

    @RestController
    static class Echo {
        @PostMapping("/api/echo")
        String echo(@RequestBody String body) {
            return body;
        }
    }

    /** 앞단에서 Content-Length를 지워 chunked 요청처럼 보이게 한다. */
    private static final Filter HIDE_LENGTH = (req, res, chain) -> chain.doFilter(new HttpServletRequestWrapper((HttpServletRequest) req) {
        @Override
        public int getContentLength() {
            return -1;
        }

        @Override
        public long getContentLengthLong() {
            return -1;
        }

        @Override
        public String getHeader(String name) {
            return "Content-Length".equalsIgnoreCase(name) ? null : super.getHeader(name);
        }
    }, res);

    private final MockMvc mvc = MockMvcBuilders.standaloneSetup(new Echo())
            .setControllerAdvice(new ApiExceptionHandler())
            .addFilters(HIDE_LENGTH, new BodySizeLimitFilter(16))
            .build();

    @Test
    void chunkedBodyOverTheLimitIs413() throws Exception {
        mvc.perform(post("/api/echo").contentType(MediaType.TEXT_PLAIN).content("x".repeat(64)))
                .andExpect(status().isContentTooLarge())
                .andExpect(content().string(containsString("ERR_PAYLOAD_TOO_LARGE")))
                .andExpect(content().string(containsString("요청 본문이 16바이트를 넘음")));
    }

    @Test
    void chunkedBodyWithinTheLimitIsRead() throws Exception {
        mvc.perform(post("/api/echo").contentType(MediaType.TEXT_PLAIN).content("small"))
                .andExpect(status().isOk())
                .andExpect(content().string("small"));
    }
}
