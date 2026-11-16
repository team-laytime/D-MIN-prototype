package com.dmin;

import static org.hamcrest.Matchers.containsString;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.test.web.servlet.MockMvc;

/**
 * 앱 전체가 뜨는지(빈 연결)와 설정이 실제로 먹는지 본다. DB는 없다: 접속은 처음 쓸 때 하므로 뜨는 데는 필요 없다.
 * - 스케줄러 스레드 4개: 계산(poll)이 한 스레드를 오래 잡아도 맥박(heartbeat)이 돈다
 * - 본문 한도 필터가 실제 필터 사슬에 들어 있다
 */
@SpringBootTest(properties = {
    "spring.datasource.url=jdbc:postgresql://127.0.0.1:1/none",
    "spring.datasource.username=none",
    "spring.datasource.password=none",
    "dmin.runs.worker-enabled=false"
})
@AutoConfigureMockMvc
class ServerContextTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    ThreadPoolTaskScheduler scheduler;

    @Test
    void schedulerHasRoomForTheHeartbeat() {
        assertEquals(4, scheduler.getScheduledThreadPoolExecutor().getCorePoolSize());
        assertEquals("dmin-sched-", scheduler.getThreadNamePrefix());
    }

    @Test
    void bodyLimitFilterIsInTheChain() throws Exception {
        mvc.perform(post("/api/cases").contentType(MediaType.APPLICATION_JSON).content(new byte[10 * 1024 * 1024 + 1]))
                .andExpect(status().isContentTooLarge())
                .andExpect(content().string(containsString("ERR_PAYLOAD_TOO_LARGE")));
        // 한도 안의 잘못된 JSON은 그대로 400
        mvc.perform(post("/api/runs").contentType(MediaType.APPLICATION_JSON).content("{\"case_id\": \"x\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(content().string(containsString("ERR_VALIDATION")));
    }
}
