# 잔여 객체별 검증 단위

2026-10-05. 모든 단위는 원본→SQL 뷰의 값·키 검증과 SQL→그래프의 동일 조건 결과 비교를 함께 요구한다. SQL 배포만으로 완료하지 않는다. 결과 파일은 `output/ontology-views-puppygraph-20261005/`에 둔다.

| 단위 | 객체와 직접 링크 | 합격 조건 | SQL 기준 |
|---|---|---|---|
| 18-01 | Concept, 상위 개념 | ID·속성 일치; 실제 부모만 연결; 부모 부재는 무연결 | concept 원본 키와 parent_concept_id |
| 18-02 | EventThread, 사건 소속 | 사건별 소속 일치; NULL 상태 보존; 역방향 일치 | event_thread, event_thread_link |
| 18-03 | DailyNAV, ETF | 날짜·좌당 값 일치; Decimal 손실 없음; ETF 연결 일치 | etf_nav_daily 복합키 |
| 18-04 | DailyInvestorFlow, Security | 날짜·투자자별 값 보존; Equity/ETF 구별; 합계 범위 추정 금지 | investor_flow_daily 복합키 |
| 18-05 | IntradayInvestorFlow, Equity | 원본 시점·수치 보존; 관측 시각 추정 금지; 연결 일치 | investor_flow_intraday 복합키 |
| 18-06 | DailyBar, Security | 종가·거래량·기준 일치; OHLC NULL; 날짜/증권 분할로 키 검증 | price_daily PK, instrument_id·trade_date 조건 |
| 18-07 | ExchangeSecurityClassification, Security | 시장·티커로 ID 해소; 다중 일치 실패; 분류 값 일치 | exchange_security_classification 원본 매핑 |
| 18-08 | SecurityIndustryClassification, Security | 분류 값·수집 시점 보존; 적용일 추정 금지; 타입 연결 일치 | instrument_classification |
| 18-09 | SecurityListingSnapshot, Security | 상장·주식종류 값 보존; ID 일치; 타입 연결 일치 | instrument_classification |
| 18-10 | MarketCapitalization, Security | 미확정 금액·통화 NULL; 기록 키 유지; 값 부재 표시 | instrument_classification |
| 18-11 | MarketIndex, ETF 추종 | INDEX 원본만 사용; 실제 대상만 연결; 현재 빈 데이터 표시 | market_series의 series_type=INDEX |
| 18-12 | FinancialReportSnapshot, Company | 수집본 식별 보존; 회사 코드 해소; 연간/기간 표시 일치 | financial_report_version 복합키 |
| 18-13 | FinancialMetric, Company·보고 문맥·직접 출처 | 값·기간·회계·판본 보존; 계산값에 직접 출처 부여 금지; 입력 링크 보류 유지 | financial_metric 및 완전한 report 복합키 |
| 18-14 | ReportedBusinessSegment, 공시·개념 | 원문 기간·금액 보존; 미확정 분모·범위 NULL; 실제 공시 연결 | business_segment_fact와 disclosure_fact 전체 FK |
| 18-15 | MacroObservation | 관측일·가용 시점·값 일치; 알려진 지역 매핑만 사용; Decimal 정밀도 보존 | macro_observation 복합키 |

공통 실행: `test_all_graph.py`는 각 객체의 모든 속성 표본과 각 링크의 선택 대상에 연결된 모든 기록을 정방향·역방향으로 비교한다. 전체 데이터 정합성 감사와 기본 CQ 시험은 별도로 실행한다. 빈 데이터 통과를 해당 업무 사례 검증으로 세지 않는다.

추가 확인: PuppyGraph 1.13.0 Decimal은 Bolt 반환 시 float로 변환되어 큰 금액이 손실됐다. SQL numeric은 유지하고 명시된 decimal_text 전송 컬럼으로 그래프에 정확한 문자열을 전달한다. 숫자 계산은 SQL 또는 Decimal 파서가 있는 계산 툴에서 수행하며 문자열 비교·float 변환은 허용하지 않는다.
