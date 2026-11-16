package com.dmin.cases;

import com.dmin.common.error.DminException;
import com.dmin.common.error.ErrorCode;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 데이터 넣는 곳. 둘 중 하나로 넣는다.
 * <ul>
 *   <li>POST /api/cases — 요청 JSON 본문 그대로 (data/README.md의 계약)</li>
 *   <li>POST /api/cases/import — 파일 업로드(.json 또는 .csv). CSV는 입항 건만 있으면 된다</li>
 * </ul>
 * 같은 내용을 다시 넣으면 새로 만들지 않고 기존 것을 돌려준다(duplicate=true).
 */
@RestController
class CaseController {

    private final CaseService cases;

    CaseController(CaseService cases) {
        this.cases = cases;
    }

    @PostMapping(path = "/cases", consumes = MediaType.APPLICATION_JSON_VALUE)
    ResponseEntity<CaseService.CaseView> create(@RequestBody String body) {
        CaseService.CaseView v = cases.importJson(body, null);
        return ResponseEntity.status(v.duplicate() ? HttpStatus.OK : HttpStatus.CREATED).body(v);
    }

    @PostMapping(path = "/cases/import", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    ResponseEntity<CaseService.CaseView> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(name = "title", required = false) String title,
            @RequestParam(name = "plan_start", required = false) String planStart,
            @RequestParam(name = "plan_end", required = false) String planEnd)
            throws IOException {
        String name = file.getOriginalFilename() == null ? "upload" : file.getOriginalFilename();
        String text = new String(file.getBytes(), StandardCharsets.UTF_8);
        String lower = name.toLowerCase(Locale.ROOT);
        CaseService.CaseView v;
        if (lower.endsWith(".csv")) {
            v = cases.importCsv(text, name, title, planStart, planEnd);
        } else if (lower.endsWith(".json")) {
            v = cases.importJson(text, name);
        } else {
            throw new DminException(ErrorCode.VALIDATION, ".json 또는 .csv 파일만 받습니다: " + name);
        }
        return ResponseEntity.status(v.duplicate() ? HttpStatus.OK : HttpStatus.CREATED).body(v);
    }

    @GetMapping("/cases")
    List<CaseService.CaseView> list(@RequestParam(defaultValue = "50") int limit) {
        return cases.list(Math.clamp(limit, 1, 200));
    }

    @GetMapping("/cases/{id}")
    CaseService.CaseView get(@PathVariable long id) {
        return cases.get(id, false);
    }

    @GetMapping(path = "/cases/{id}/payload", produces = MediaType.APPLICATION_JSON_VALUE)
    String payload(@PathVariable long id) {
        return cases.payload(id);
    }
}
