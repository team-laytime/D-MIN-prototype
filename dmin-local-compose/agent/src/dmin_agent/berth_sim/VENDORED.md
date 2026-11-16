# 팀원 코드 복사본 (berth_sim)

- 복사한 날: 2026-11-16 14:47 · 원본: `~/Downloads/berth_sim_share/berth_sim` · 복사: `scripts/sync-team-engine.sh`
- **이 폴더의 .py는 고치지 않는다.** 원본에서 고친 뒤 다시 복사한다. 우리 요청 → 이 코드로 바꾸는 일은 `../team_engine.py`가 한다.
- 원본 README의 실행 방법(start.command · serve_cpsat.py)은 여기서 쓰지 않는다. 엑셀(openpyxl)을 읽는 sample_loader·master_data.load_master도 부르지 않는다.

| 파일 | sha256 앞 16자 | 줄 |
|---|---|---|
| __init__.py | e3b0c44298fc1c14 | 0 |
| berth_availability.py | 7909726f05afee2b | 34 |
| berth_fit.py | 3c1f758d99ca5dc7 | 56 |
| cli.py | 6e26b192698c2c8e | 129 |
| cost_table.py | eacc225f58bf7105 | 96 |
| cpsat_model.py | 7df31093b6ea625e | 616 |
| dummy_data.py | bcd87c9f7f4605d4 | 154 |
| feasibility.py | 80a377b684f391b9 | 192 |
| master_data.py | 8ad38b54697c76dc | 135 |
| models.py | fabfd35b7887f3e6 | 31 |
| optimizer.py | 831f00dd19c75111 | 162 |
| overrides.py | 93e770874c64fe89 | 24 |
| product_direction.py | b7d58201d4f5d7d7 | 60 |
| report_cpsat.py | b5a15d03602a2c94 | 472 |
| report_feasibility.py | b320b3d9e7248e47 | 250 |
| report_workflow.py | d2b6bf040c1926dc | 616 |
| sample_loader.py | a3b4ed5453cd875c | 48 |
| scenario.py | 4ffefc2ce6be31eb | 158 |
| shifting.py | 00def1fb3bb61179 | 57 |
| step1_prev_fix.py | 61d4f6855da04bf1 | 156 |
| step2_night_pilot.py | b1b154df8e970904 | 84 |
| step3_berth_block.py | 84254e0e1e7e2ae3 | 72 |
| step3_berth_pair.py | 2cd32fdbae10b8ff | 49 |
| step3_cargo_group.py | d9ea3ff97aad51f4 | 72 |
| sun.py | 3e38aa3e5422595f | 53 |
| synth.py | b49002097a2d6ced | 218 |
| tanks.py | b95f3ba1989c0c31 | 184 |
| tier_run.py | 06cf93f8a5895318 | 77 |
| typhoon.py | 00bf8dd3e66e919c | 388 |
| validate.py | 8c6b81e45ee02212 | 136 |
| vessel_specs.py | 085b30ee3480ba22 | 111 |
| weather.py | 9ee09acdbf7cbe3a | 214 |
| after_etb/__init__.py | c2faab98a11e2ed0 | 17 |
| after_etb/common.py | 878ad84ea1e1e183 | 14 |
| after_etb/pipeline.py | 5aa2cdd116468cd7 | 86 |
| after_etb/s10_weather_hours.py | c3551a9b7623a0c4 | 38 |
| after_etb/s11_demurrage_time.py | 51fa587a654d924b | 15 |
| after_etb/s12_demurrage_fee.py | cdccfcdc370209d0 | 20 |
| after_etb/s1_work_start.py | c97df6c349b0a9fb | 21 |
| after_etb/s2_work_finish.py | a6075c142b7edde8 | 133 |
| after_etb/s3_etu.py | 2844792f07ed8fa8 | 9 |
| after_etb/s4_hose_off.py | 789b12cda950f576 | 13 |
| after_etb/s5_etanr.py | 1b360e2f1f0ff209 | 16 |
| after_etb/s6_daylight.py | f8441e6fef3bd929 | 17 |
| after_etb/s7_laytime_start_no_daylight.py | e0167ca90e3543f8 | 57 |
| after_etb/s8_laytime_start_daylight.py | 0176cac64f475892 | 49 |
| after_etb/s9_laytime_end.py | 2d10e5f0ebf51a99 | 21 |
