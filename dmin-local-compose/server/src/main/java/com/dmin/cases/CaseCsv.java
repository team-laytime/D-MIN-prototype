package com.dmin.cases;

import com.dmin.laytime.Times;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

/**
 * 입항 건 CSV(엑셀에서 그대로 저장한 것) → 요청 JSON. 한 줄 = 입항 건 하나. 머리글은 data/templates/arrivals.csv 그대로다.
 * 부두 제약·탱크·일출몰처럼 표 하나로 못 담는 것은 JSON으로 넣는다. CSV는 '입항 건만 있으면 바로 돌려 보는' 길이다.
 * 오류 위치는 두 가지로 나온다: 여기서 바꿀 때의 칸 오류(숫자·true/false가 아님)는 'N행'(머리글 = 1행, 빈 줄은 세지 않음),
 * 바꾼 뒤 입력 검사(CaseParser)의 오류는 'arrivals[n] (id)' — n번째 입항 건 = n + 1행.
 */
final class CaseCsv {

    static final List<String> COLUMNS = List.of(
            "id", "vessel", "class", "biz", "cargo_group", "qty", "eta", "nor_tender", "grt", "dwt", "loa", "pbl", "draft",
            "laycan_from", "laycan_to", "laytime_h", "rate_usd_day", "cfr", "weather_half", "rate_per_h", "work_hours", "status",
            "fix_berth", "fix_etb", "berths");
    private static final List<String> REQUIRED = List.of(
            "id", "class", "biz", "cargo_group", "eta", "grt", "dwt", "loa", "pbl", "draft", "laycan_from", "laycan_to",
            "laytime_h", "rate_usd_day");
    private static final List<String> NUMBERS = List.of(
            "qty", "grt", "dwt", "loa", "pbl", "draft", "laytime_h", "rate_usd_day", "rate_per_h", "work_hours");

    private CaseCsv() {}

    record Converted(ObjectNode doc, List<String> errors) {}

    static Converted convert(ObjectMapper json, String text, String caseId, String title, String planStart, String planEnd) {
        List<String> errors = new ArrayList<>();
        List<List<String>> rows = parse(text.startsWith("﻿") ? text.substring(1) : text);
        rows.removeIf(r -> r.stream().allMatch(String::isBlank));
        if (rows.isEmpty()) {
            errors.add("CSV가 비어 있음");
            return new Converted(null, errors);
        }
        List<String> header = rows.getFirst().stream().map(h -> h.strip().toLowerCase(Locale.ROOT)).toList();
        Map<String, Integer> col = new HashMap<>();
        for (int i = 0; i < header.size(); i++) {
            col.put(header.get(i), i);
        }
        for (String r : REQUIRED) {
            if (!col.containsKey(r)) {
                errors.add("CSV 머리글에 '" + r + "' 열이 없음 (data/templates/arrivals.csv 참고)");
            }
        }
        for (String h : header) {
            if (!h.isBlank() && !COLUMNS.contains(h)) {
                errors.add("알 수 없는 열 '" + h + "'");
            }
        }
        if (!errors.isEmpty()) {
            return new Converted(null, errors);
        }
        ArrayNode arrivals = json.createArrayNode();
        Long minEta = null;
        for (int n = 1; n < rows.size(); n++) {
            List<String> r = rows.get(n);
            String where = (n + 1) + "행";
            ObjectNode a = json.createObjectNode();
            ObjectNode contract = json.createObjectNode();
            ObjectNode work = json.createObjectNode();
            ObjectNode fix = json.createObjectNode();
            for (String h : header) {
                String v = cell(r, col.get(h));
                if (v.isEmpty()) {
                    continue;
                }
                switch (h) {
                    case "laycan_from", "laycan_to" -> contract.put(h, v);
                    case "laytime_h", "rate_usd_day" -> putNumber(contract, h, v, where, errors);
                    case "cfr", "weather_half" -> contract.put(h, bool(v, where + " " + h, errors));
                    case "rate_per_h" -> putNumber(work, "rate_per_h", v, where, errors);
                    case "work_hours" -> putNumber(work, "hours", v, where, errors);
                    case "fix_berth" -> fix.put("berth", v);
                    case "fix_etb" -> fix.put("etb", v);
                    case "berths" -> {
                        ArrayNode bs = a.putArray("berths");
                        for (String b : v.split("[;|]")) {
                            if (!b.isBlank()) {
                                bs.add(b.strip());
                            }
                        }
                    }
                    default -> {
                        if (NUMBERS.contains(h)) {
                            putNumber(a, h, v, where, errors);
                        } else {
                            a.put(h, v);
                        }
                    }
                }
            }
            a.set("contract", contract);
            a.set("work", work);
            if (!fix.isEmpty()) {
                a.set("fix", fix);
            }
            arrivals.add(a);
            String eta = cell(r, col.get("eta"));
            try {
                long t = Times.parse(eta);
                minEta = minEta == null ? t : Math.min(minEta, t);
            } catch (IllegalArgumentException ignored) {
                // 행 번호가 아니라 CaseParser가 'arrivals[n] (id).eta' 꼴로 알려 준다
            }
        }
        ObjectNode doc = json.createObjectNode();
        doc.put("id", caseId);
        doc.put("title", title);
        ObjectNode plan = doc.putObject("plan");
        // 기간을 주지 않으면 가장 이른 ETA의 그날 0시부터 7일
        String start = planStart != null && !planStart.isBlank()
                ? planStart
                : (minEta == null ? null : Times.iso(Times.day0(minEta)));
        String end = planEnd != null && !planEnd.isBlank()
                ? planEnd
                : (start == null ? null : Times.iso(Times.parse(start) + 7 * Times.DAY));
        if (start != null) {
            plan.put("start", start);
        }
        if (end != null) {
            plan.put("end", end);
        }
        doc.set("arrivals", arrivals);
        doc.putArray("restrictions");
        doc.putArray("inventory");
        return new Converted(doc, errors);
    }

    private static String cell(List<String> row, Integer i) {
        return i == null || i >= row.size() ? "" : row.get(i).strip();
    }

    private static void putNumber(ObjectNode node, String field, String v, String where, List<String> errors) {
        try {
            node.put(field, Double.parseDouble(v.replace(",", "")));
        } catch (NumberFormatException e) {
            errors.add(where + " " + field + "가 숫자가 아님: '" + v + "'");
        }
    }

    private static boolean bool(String v, String where, List<String> errors) {
        return switch (v.toLowerCase(Locale.ROOT)) {
            case "true", "y", "yes", "1", "o" -> true;
            case "false", "n", "no", "0", "x" -> false;
            default -> {
                errors.add(where + "는 true/false: '" + v + "'");
                yield false;
            }
        };
    }

    /** RFC 4180 CSV: 큰따옴표 안의 쉼표·줄바꿈, "" 이스케이프를 처리한다. */
    static List<List<String>> parse(String text) {
        List<List<String>> rows = new ArrayList<>();
        List<String> row = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (quoted) {
                if (ch == '"') {
                    if (i + 1 < text.length() && text.charAt(i + 1) == '"') {
                        cur.append('"');
                        i++;
                    } else {
                        quoted = false;
                    }
                } else {
                    cur.append(ch);
                }
            } else if (ch == '"') {
                quoted = true;
            } else if (ch == ',') {
                row.add(cur.toString());
                cur.setLength(0);
            } else if (ch == '\n' || ch == '\r') {
                if (ch == '\r' && i + 1 < text.length() && text.charAt(i + 1) == '\n') {
                    i++;
                }
                row.add(cur.toString());
                cur.setLength(0);
                rows.add(row);
                row = new ArrayList<>();
            } else {
                cur.append(ch);
            }
        }
        if (cur.length() > 0 || !row.isEmpty()) {
            row.add(cur.toString());
            rows.add(row);
        }
        return rows;
    }
}
