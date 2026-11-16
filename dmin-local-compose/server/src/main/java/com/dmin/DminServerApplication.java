package com.dmin;

import java.util.Arrays;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@ConfigurationPropertiesScan
@EnableScheduling
public class DminServerApplication {

    public static void main(String[] args) {
        // migrate 프로필: Flyway만 돌리고 끝난다. Compose의 dmin-migrate 컨테이너가 마이그레이션 계정으로 이렇게 띄운다.
        boolean migrateOnly = Arrays.asList(args).contains("--migrate")
                || "migrate".equals(System.getenv("SPRING_PROFILES_ACTIVE"));
        if (migrateOnly) {
            SpringApplication app = new SpringApplication(DminServerApplication.class);
            app.setAdditionalProfiles("migrate");
            System.exit(SpringApplication.exit(app.run(args)));
        }
        SpringApplication.run(DminServerApplication.class, args);
    }
}
