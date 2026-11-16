package com.dmin.publicdata;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.StringJoiner;
import org.springframework.stereotype.Component;

/**
 * 공공데이터포털 GET 한 번. 키는 여기서만 URL에 붙는다.
 * Decoding 키에는 + / = 가 들어 있어 값마다 직접 URL 인코딩한다(그대로 두면 +가 공백으로 읽혀 인증 오류가 난다).
 */
@Component
class PublicDataClient {

    private final PublicDataProperties props;
    private final HttpClient http;

    PublicDataClient(PublicDataProperties props) {
        this.props = props;
        this.http = HttpClient.newBuilder()
                .connectTimeout(props.timeout())
                .version(HttpClient.Version.HTTP_1_1)
                .build();
    }

    boolean configured() {
        return props.configured();
    }

    byte[] get(String path, Map<String, String> params) {
        if (!props.configured()) {
            throw new PublicDataException("PUBLIC_DATA_SERVICE_KEY가 없습니다 (.env)");
        }
        Map<String, String> all = new LinkedHashMap<>();
        all.put("serviceKey", props.serviceKey().strip());
        all.putAll(params);
        StringJoiner q = new StringJoiner("&");
        all.forEach((k, v) -> q.add(enc(k) + "=" + enc(v)));
        HttpRequest req;
        try {
            URI uri = URI.create(props.baseUrl() + path + "?" + q);
            req = HttpRequest.newBuilder(uri).timeout(props.timeout()).GET().build();
        } catch (IllegalArgumentException e) {
            // 원래 메시지에는 키가 든 주소가 통째로 들어 있다 → 버리고 설정 이름만 알려 준다
            throw new PublicDataException("공공데이터포털 주소 형식 오류 (dmin.public-data.base-url 확인)");
        }
        HttpResponse<byte[]> resp;
        try {
            resp = http.send(req, HttpResponse.BodyHandlers.ofByteArray());
        } catch (IOException e) {
            throw new PublicDataException("공공데이터포털 호출 실패: " + e.getClass().getSimpleName());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new PublicDataException("공공데이터포털 호출 중단");
        }
        if (resp.statusCode() != 200) {
            throw new PublicDataException("공공데이터포털 응답 " + resp.statusCode());
        }
        return resp.body();
    }

    private static String enc(String v) {
        return URLEncoder.encode(v, StandardCharsets.UTF_8);
    }
}
