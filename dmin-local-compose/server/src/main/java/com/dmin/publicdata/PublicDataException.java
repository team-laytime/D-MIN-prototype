package com.dmin.publicdata;

/** 공공데이터포털 호출 실패. 메시지에는 키가 든 URL을 넣지 않는다. */
public class PublicDataException extends RuntimeException {

    public PublicDataException(String message) {
        super(message);
    }
}
