package com.dmin.cases;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.dmin.laytime.CaseParser;
import com.dmin.laytime.Rules;
import java.util.List;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

/** CSV 한 줄 = 입항 건 하나. 엑셀에서 저장한 그대로(BOM·따옴표 안 쉼표)도 읽고, 틀린 칸은 행 번호와 함께 알려 준다. */
class CaseCsvTest {

    private final JsonMapper json = JsonMapper.builder().build();
    private static final String HEAD =
            "id,vessel,class,biz,cargo_group,qty,eta,grt,dwt,loa,pbl,draft,laycan_from,laycan_to,laytime_h,rate_usd_day,rate_per_h,status,fix_berth,fix_etb\n";

    @Test
    void csvBecomesTheSameRequestShapeAndPassesTheParser() {
        String csv = "﻿" + HEAD
                + "A,\"MR, DSL\",PP,EX,DSL,\"300,000\",2026-11-10T06:00,29597,45000,183,85.5,12.64,2026-11-10T00:00,2026-11-11T23:59,36,26252,11145,,,\n"
                + "F,LR1,PP,EX,DSL,500000,2026-11-11T20:00,42141,75000,227,117.9,14.16,2026-11-11T00:00,2026-11-12T23:59,36,24312,12319,FIX,#8,2026-11-12T08:00\n";
        CaseCsv.Converted c = CaseCsv.convert(json, csv, "CSV-t", "t", null, null);
        assertTrue(c.errors().isEmpty(), c.errors()::toString);
        assertEquals("2026-11-10T00:00", c.doc().get("plan").get("start").asString());
        assertEquals("2026-11-17T00:00", c.doc().get("plan").get("end").asString());
        assertEquals("MR, DSL", c.doc().get("arrivals").get(0).get("vessel").asString());
        assertEquals(300000.0, c.doc().get("arrivals").get(0).get("qty").doubleValue());
        assertEquals("#8", c.doc().get("arrivals").get(1).get("fix").get("berth").asString());
        CaseParser.Parsed p = CaseParser.parse(c.doc(), Rules.bundled());
        assertTrue(p.ok(), p.errors()::toString);
        assertEquals(2, p.data().arrivals().size());
    }

    @Test
    void missingColumnsStopBeforeReadingRows() {
        CaseCsv.Converted c = CaseCsv.convert(json, "id,vessel\nA,x\n", "CSV-t", "t", null, null);
        assertTrue(c.doc() == null);
        assertTrue(c.errors().stream().anyMatch(e -> e.contains("'class'")));
    }

    @Test
    void parserReportsEveryBadCellWithItsRow() {
        String csv = HEAD + "X1,v,ZZ,EX,DSL,1,2026-11-10T09:00+09:00,29597,45000,183,85.5,12.64,2026-11-10T00:00,2026-11-11T23:59,36,26252,11145,,,\n";
        CaseCsv.Converted c = CaseCsv.convert(json, csv, "CSV-t", "t", "2026-11-10T00:00", "2026-11-12T00:00");
        List<String> errs = CaseParser.parse(c.doc(), Rules.bundled()).errors();
        assertTrue(errs.stream().anyMatch(e -> e.contains("class")), errs::toString);
        assertTrue(errs.stream().anyMatch(e -> e.contains("시간대")), errs::toString);
    }
}
