package com.dmin.common.error;

import com.dmin.common.web.BodySizeLimitFilter;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

/** 오류는 RFC 9457 ProblemDetail + code (D-MIN-server와 같다). 입력 검증 오류는 errors[]에 항목별로 담는다. */
@RestControllerAdvice
class ApiExceptionHandler extends ResponseEntityExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(DminException.class)
    ProblemDetail handleDmin(DminException ex) {
        ProblemDetail problem = problem(ex.errorCode(), ex.errorCode().status(), ex.getMessage());
        if (!ex.details().isEmpty()) {
            problem.setProperty("errors", ex.details());
        }
        return problem;
    }

    // 예상 못 한 예외: 원인은 로그에만 남기고 내부 내용은 응답에 넣지 않는다.
    @ExceptionHandler(Exception.class)
    ProblemDetail handleUnexpected(Exception ex) {
        log.error("Unhandled exception", ex);
        return problem(ErrorCode.INTERNAL, ErrorCode.INTERNAL.status(), null);
    }

    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(
            MethodArgumentNotValidException ex, HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        ProblemDetail body = ex.getBody();
        List<FieldViolation> errors = ex.getBindingResult().getFieldErrors().stream()
                .map(error -> new FieldViolation(error.getField(), error.getDefaultMessage()))
                .toList();
        body.setProperty("errors", errors);
        return handleExceptionInternal(ex, body, headers, status, request);
    }

    // 길이를 모르는 본문(chunked)이 한도를 넘으면 BodySizeLimitFilter가 읽는 도중에 끊는다 → 400이 아니라 413.
    @Override
    protected ResponseEntity<Object> handleHttpMessageNotReadable(
            HttpMessageNotReadableException ex, HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        for (Throwable t = ex; t != null; t = t.getCause()) {
            if (t instanceof BodySizeLimitFilter.TooLargeException tooLarge) {
                HttpStatusCode tooLargeStatus = ErrorCode.PAYLOAD_TOO_LARGE.status();
                ProblemDetail body = ProblemDetail.forStatusAndDetail(tooLargeStatus, tooLarge.getMessage());
                body.setTitle("Payload Too Large"); // Content-Length로 끊을 때(필터가 바로 쓰는 본문)와 같은 모양
                return handleExceptionInternal(ex, body, headers, tooLargeStatus, request);
            }
        }
        return super.handleHttpMessageNotReadable(ex, headers, status, request);
    }

    // Spring MVC가 직접 던지는 오류는 모두 여기를 거친다.
    @Override
    protected ResponseEntity<Object> handleExceptionInternal(
            Exception ex, Object body, HttpHeaders headers, HttpStatusCode statusCode, WebRequest request) {
        ResponseEntity<Object> response = super.handleExceptionInternal(ex, body, headers, statusCode, request);
        if (response != null && response.getBody() instanceof ProblemDetail problem) {
            problem.setProperty("code", ErrorCode.forStatus(statusCode).code());
        }
        return response;
    }

    private static ProblemDetail problem(ErrorCode errorCode, HttpStatusCode status, String detail) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(status, detail);
        problem.setProperty("code", errorCode.code());
        return problem;
    }

    record FieldViolation(String field, String message) {}
}
