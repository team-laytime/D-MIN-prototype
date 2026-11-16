package com.dmin.common.error;

import java.util.List;

/** 클라이언트에게 보여줄 오류. 메시지가 응답의 {@code detail}이 되고, details는 errors[]로 나간다. */
public class DminException extends RuntimeException {

    private final ErrorCode errorCode;
    private final List<String> details;

    public DminException(ErrorCode errorCode, String detail) {
        this(errorCode, detail, List.of());
    }

    public DminException(ErrorCode errorCode, String detail, List<String> details) {
        super(detail);
        this.errorCode = errorCode;
        this.details = List.copyOf(details);
    }

    public ErrorCode errorCode() {
        return errorCode;
    }

    public List<String> details() {
        return details;
    }
}
