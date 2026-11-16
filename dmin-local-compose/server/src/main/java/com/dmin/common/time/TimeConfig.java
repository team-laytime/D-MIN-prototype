package com.dmin.common.time;

import java.time.Clock;
import java.time.ZoneId;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
class TimeConfig {

    // 현재 시각(공공데이터 캐시·조회 창)은 이 빈으로 얻는다. 테스트에서는 Clock.fixed로 고정한다.
    @Bean
    Clock clock() {
        return Clock.system(ZoneId.of("Asia/Seoul"));
    }
}
