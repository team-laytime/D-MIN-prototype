package com.dmin.common.web;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.PathMatchConfigurer;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration(proxyBeanMethods = false)
class WebConfig implements WebMvcConfigurer {

    // 입구(Caddy)가 /api를 그대로 넘기므로 우리 컨트롤러는 /api 아래에 둔다.
    // com.dmin.internal은 예외다: Caddy가 넘기지 않는 경로(/internal/**)라 밖에서는 닿지 않는다(수집 타이머 컨테이너만 부른다).
    @Override
    public void configurePathMatch(PathMatchConfigurer configurer) {
        configurer.addPathPrefix("/api", type -> {
            String pkg = type.getPackageName();
            return pkg.startsWith("com.dmin") && !pkg.startsWith("com.dmin.internal");
        });
    }
}
