package com.dmin.publicdata;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/**
 * 공공데이터포털 연결 설정. 키(Decoding 키)는 환경변수 PUBLIC_DATA_SERVICE_KEY → .env(커밋 안 됨)에서만 온다.
 * 키는 응답·로그·오류 문구에 넣지 않는다(demo/docs/16 '키 관리 원칙').
 */
@ConfigurationProperties("dmin.public-data")
public record PublicDataProperties(
        @DefaultValue("") String serviceKey,
        @DefaultValue("https://apis.data.go.kr") String baseUrl,
        @DefaultValue("30s") Duration aisCache,
        @DefaultValue("5m") Duration entryCache,
        @DefaultValue("5m") Duration voyageCache,
        @DefaultValue("20s") Duration timeout) {

    public boolean configured() {
        return serviceKey != null && !serviceKey.isBlank();
    }
}
