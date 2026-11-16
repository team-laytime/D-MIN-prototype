"""ETB 산정 이후 계산식 (pptx 10~12번째 슬라이드, 쪽번호 09~11).

흐름도 박스 하나당 파일 하나:
  s1_work_start                 ETB 有? / 예상시작시간 有? / 부두 지정?
  s2_work_finish                평균 Rate 산출, 작업완료시간 산출
  s3_etu                        예상이안시간 = 작업완료시간 + 2h
  s4_hose_off                   호스분리시간 = 완료시간 + 30분
  s5_etanr                      ETA & NR Tender 有? / ETANR = NVL(NR_TENDER, ETA)
  s6_daylight                   Day Light 적용?
  s7_laytime_start_no_daylight  정박개시 (Daylight 미적용)
  s8_laytime_start_daylight     정박개시 (Daylight 적용)
  s9_laytime_end                LayTime 有? / 원유 && CFR False / 정박종료
  s10_weather_hours             기상체선 시간 (기상 부두 제약 ∩ [정박종료, 호스분리])
  s11_demurrage_time            Demurrage Time = 호스분리 - 정박종료 - 기상체선/2
  s12_demurrage_fee             체선료 = Demurrage Time * Rate / 24, 시나리오 합계
pipeline.py 가 위 순서대로 묶는다.
"""
