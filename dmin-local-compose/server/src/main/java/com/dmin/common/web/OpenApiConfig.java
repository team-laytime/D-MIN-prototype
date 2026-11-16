package com.dmin.common.web;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
class OpenApiConfig {

    @Bean
    OpenAPI dminOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("D-MIN API")
                        .description("접안 일정과 예상 체선료 비교 API. 오류는 RFC 9457 ProblemDetail에 code를 더해 돌려준다.")
                        .version("v0"));
    }
}
