package com.dmin.publicdata;

import com.dmin.common.error.DminException;
import com.dmin.common.error.ErrorCode;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 화면이 부르는 공공데이터 경로 (= demo FastAPI의 /api/ais/*·/api/entry/* 와 같은 경로·같은 JSON 모양).
 * 그래서 GitHub Pages 프로토타입의 '실시간 AIS 보기'가 고치지 않고 이 서버에 붙는다. 키는 서버에만 있다.
 */
@RestController
class PublicDataController {

    private final AisService ais;
    private final EntryService entry;
    private final PublicDataProperties props;

    PublicDataController(AisService ais, EntryService entry, PublicDataProperties props) {
        this.ais = ais;
        this.entry = entry;
        this.props = props;
    }

    /** 울산항 항내 선박 위치. bbox=남,서,북,동 */
    @GetMapping("/ais/vessels")
    ResponseEntity<Map<String, Object>> vessels(
            @RequestParam(name = "max_age_min", defaultValue = "60") double maxAgeMin,
            @RequestParam(required = false) String bbox) {
        if (!(maxAgeMin > 0 && maxAgeMin <= 1440)) { // NaN도 여기서 걸린다
            throw new DminException(ErrorCode.VALIDATION, "max_age_min은 0보다 크고 1440(하루) 이하인 분입니다");
        }
        double[] box = null;
        if (bbox != null && !bbox.isBlank()) {
            String[] p = bbox.split(",");
            if (p.length != 4) {
                throw new DminException(ErrorCode.VALIDATION, "bbox는 '남,서,북,동' 숫자 4개입니다");
            }
            box = new double[4];
            try {
                for (int i = 0; i < 4; i++) {
                    box[i] = Double.parseDouble(p[i].strip());
                }
            } catch (NumberFormatException e) {
                throw new DminException(ErrorCode.VALIDATION, "bbox는 '남,서,북,동' 숫자 4개입니다");
            }
        }
        try {
            return ResponseEntity.ok(ais.vessels(maxAgeMin, box));
        } catch (PublicDataException e) {
            return unavailable(e, "vessels");
        }
    }

    /** 한 척의 입항·투묘·접안·이안·출항 기록. 미래 ETA는 없다. */
    @GetMapping("/ais/voyage")
    ResponseEntity<Map<String, Object>> voyage(
            @RequestParam String callsgn, @RequestParam String year, @RequestParam(required = false) String voyage) {
        if (callsgn.isBlank() || callsgn.length() > 12 || !year.matches("\\d{4}")) {
            throw new DminException(ErrorCode.VALIDATION, "callsgn은 호출부호, year는 입항연도 4자리입니다");
        }
        try {
            return ResponseEntity.ok(ais.voyage(callsgn, year, voyage));
        } catch (PublicDataException e) {
            return unavailable(e, "events");
        }
    }

    /** 울산 입항 신고. 입항일시가 지금보다 늦으면 대리점이 신고한 입항 예정(ETA)이다. */
    @GetMapping("/entry/arrivals")
    ResponseEntity<Map<String, Object>> arrivals(
            @RequestParam(required = false) String callsgn,
            @RequestParam(name = "hours_back", defaultValue = "0") double hoursBack,
            @RequestParam(name = "hours_ahead", defaultValue = "48") double hoursAhead) {
        if (callsgn != null && (callsgn.isBlank() || callsgn.length() > 12)) {
            throw new DminException(ErrorCode.VALIDATION, "callsgn은 호출부호입니다");
        }
        if (!(hoursBack >= 0 && hoursBack <= 240) || !(hoursAhead >= 0 && hoursAhead <= 240)) { // NaN도 여기서 걸린다
            throw new DminException(ErrorCode.VALIDATION, "hours_back·hours_ahead는 0~240시간입니다");
        }
        try {
            return ResponseEntity.ok(entry.arrivals(callsgn, hoursBack, hoursAhead));
        } catch (PublicDataException e) {
            return unavailable(e, "arrivals");
        }
    }

    /** 키가 들어 있는지만 알려 준다(값은 절대 내보내지 않는다). */
    @GetMapping("/public-data/status")
    Map<String, Object> status() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("configured", props.configured());
        out.put("apis", List.of("ais/vessels (15156631)", "ais/voyage (15156628)", "entry/arrivals (15006353)"));
        return out;
    }

    private static ResponseEntity<Map<String, Object>> unavailable(PublicDataException e, String listField) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("code", ErrorCode.UPSTREAM_UNAVAILABLE.code());
        body.put("error", e.getMessage());
        body.put(listField, List.of());
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(body);
    }
}
