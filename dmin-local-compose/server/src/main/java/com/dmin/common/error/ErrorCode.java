package com.dmin.common.error;

import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;

/** 클라이언트가 분기할 수 있는 고정 코드. 모든 오류 응답의 {@code code} 필드에 들어간다. (D-MIN-server와 같은 규칙 + 4개) */
public enum ErrorCode {
    VALIDATION("ERR_VALIDATION", HttpStatus.BAD_REQUEST),
    NOT_FOUND("ERR_NOT_FOUND", HttpStatus.NOT_FOUND),
    UNSUPPORTED_REQUEST("ERR_UNSUPPORTED_REQUEST", HttpStatus.METHOD_NOT_ALLOWED),
    CONFLICT("ERR_CONFLICT", HttpStatus.CONFLICT),
    // 요청 본문이 한도(dmin.web.max-body-bytes, 기본 10MB)를 넘음. BodySizeLimitFilter가 낸다.
    PAYLOAD_TOO_LARGE("ERR_PAYLOAD_TOO_LARGE", HttpStatus.CONTENT_TOO_LARGE),
    // 공공데이터 키가 없거나 원본 API가 실패했을 때. 화면은 이 코드를 보고 실시간 기능을 숨긴다.
    UPSTREAM_UNAVAILABLE("ERR_UPSTREAM_UNAVAILABLE", HttpStatus.SERVICE_UNAVAILABLE),
    INTERNAL("ERR_INTERNAL", HttpStatus.INTERNAL_SERVER_ERROR);

    private final String code;
    private final HttpStatus status;

    ErrorCode(String code, HttpStatus status) {
        this.code = code;
        this.status = status;
    }

    public String code() {
        return code;
    }

    public HttpStatus status() {
        return status;
    }

    /** Spring MVC가 직접 던지는 오류(잘못된 JSON, 없는 경로, 잘못된 메서드)에 붙일 코드. */
    static ErrorCode forStatus(HttpStatusCode status) {
        if (status.value() == HttpStatus.BAD_REQUEST.value()) {
            return VALIDATION;
        }
        if (status.value() == HttpStatus.NOT_FOUND.value()) {
            return NOT_FOUND;
        }
        if (status.value() == HttpStatus.CONTENT_TOO_LARGE.value()) { // 업로드 한도 초과(MaxUploadSizeExceededException) 등
            return PAYLOAD_TOO_LARGE;
        }
        if (status.is5xxServerError()) {
            return INTERNAL;
        }
        return UNSUPPORTED_REQUEST;
    }
}
