package com.dmin.runs;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;
import org.springframework.stereotype.Component;

/**
 * Python 에이전트 서버(dmin-agent, Compose 내부 네트워크 agent)를 부른다. 에이전트는 Spring만 부를 수 있다(그 네트워크에 둘뿐이다).
 * 에이전트는 Spring을 다시 부르지 않는다(정의서 4.3). 솔버 결과는 제안이고, 금액은 Spring이 다시 계산한다.
 */
@Component
class AgentClient {

    @ConfigurationProperties("dmin.agent")
    record Props(
            @DefaultValue("http://localhost:8000") String url,
            @DefaultValue("3s") Duration connectTimeout,
            @DefaultValue("20m") Duration solveTimeout) {}

    static class AgentException extends RuntimeException {
        AgentException(String message) {
            super(message);
        }
    }

    private final Props props;
    private final HttpClient http;

    AgentClient(Props props) {
        this.props = props;
        this.http = HttpClient.newBuilder()
                .connectTimeout(props.connectTimeout())
                .version(HttpClient.Version.HTTP_1_1)
                .build();
    }

    String url() {
        return props.url();
    }

    /** GET /health → 엔진·규칙 표 버전. */
    String health() {
        return send(HttpRequest.newBuilder(URI.create(props.url() + "/health"))
                .timeout(Duration.ofSeconds(3))
                .GET()
                .build());
    }

    /**
     * POST /v1/optimize — 요청 JSON 하나를 주고 응답 JSON 하나를 받는다 (run.optimize 계약).
     * engine: team-cpsat(팀원 코드 berth_sim) · ppt-milp(기존 엔진). 샘플 54건 기존 엔진: 쿠버네티스 판에서 약 83초 · 호스트 약 97초.
     */
    String optimize(String caseJson, int top, int timeLimitS, String engine) {
        String body = "{\"request\":" + caseJson + ",\"top\":" + top + ",\"time_limit_s\":" + timeLimitS
                + ",\"engine\":\"" + engine + "\"}";
        return send(HttpRequest.newBuilder(URI.create(props.url() + "/v1/optimize"))
                .timeout(props.solveTimeout())
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build());
    }

    private String send(HttpRequest req) {
        try {
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (resp.statusCode() != 200) {
                String b = resp.body() == null ? "" : resp.body();
                throw new AgentException("에이전트 응답 " + resp.statusCode() + ": " + b.substring(0, Math.min(300, b.length())));
            }
            return resp.body();
        } catch (IOException e) {
            throw new AgentException("에이전트 호출 실패 (" + props.url() + "): " + e.getClass().getSimpleName());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new AgentException("에이전트 호출 중단");
        }
    }
}
