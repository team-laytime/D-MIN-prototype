package com.dmin.common.json;

import com.fasterxml.jackson.annotation.JsonFormat;
import java.math.BigDecimal;
import java.time.ZoneId;
import java.util.TimeZone;
import org.springframework.boot.jackson.autoconfigure.JsonMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import tools.jackson.databind.cfg.DateTimeFeature;

@Configuration(proxyBeanMethods = false)
class JsonConfig {

    @Bean
    JsonMapperBuilderCustomizer dminJsonRules() {
        return builder -> builder
                // 소수는 문자열로 내보낸다. 브라우저에서 float로 바뀌지 않게 하기 위해서다.
                .withConfigOverride(
                        BigDecimal.class,
                        override -> override.setFormat(JsonFormat.Value.forShape(JsonFormat.Shape.STRING)))
                // 시각은 KST로 보여준다. UTC로 저장된 시각도 +09:00 오프셋으로 나간다.
                .defaultTimeZone(TimeZone.getTimeZone(ZoneId.of("Asia/Seoul")))
                .enable(DateTimeFeature.WRITE_DATES_WITH_CONTEXT_TIME_ZONE);
    }
}
