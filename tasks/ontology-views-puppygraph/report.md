# 객체 뷰와 PuppyGraph 구현 결과

2026-10-05. 현재 객체 모델의 SQL 뷰와 실제 그래프 연결을 구현했고, 기본 조사 질문을 SQL 결과와 대조했다. 전체 전망 기능이나 13개 CQ의 에이전트 평가를 완료한 결과는 아니다.

## 적용한 구조

| 구분 | 결과 |
|---|---|
| SQL 객체 뷰 | 23개, dev RDS의 ontology_view에 적용 |
| 공용 준비 뷰 | 3개: 사건 참여, 문서 사건 근거, 뉴스 증권 언급 |
| 기존 연결 원본 재사용 | event_thread_link 1개 |
| 논리 링크 | 37개 유지, 36개 그래프 매핑, CalculatedFrom 1개 보류 |
| 인터페이스 | Actor·Security·SourceDocument를 구체 타입별 단일 UNION ALL 질의로 변환 |
| 대시보드 | 물리 원본 27개를 PK/FK 테이블로 표시. 링크별 원본·컬럼·타입 조건·방향 확인 |
| 실제 그래프 | PuppyGraph 1.13.0, private ECS Fargate pilot, PostgreSQL 일반 VIEW 직접 조회 |

대시보드는 http://127.0.0.1:5186/view-design 에 있다. 참여 준비 뷰는 새 업무 객체가 아니다. 관계를 역방향으로 읽기 위한 중복 엣지도 만들지 않았다. 일봉 OHLC는 요청대로 보류했으며 종가로 대체하지 않았다.

## 실제 실행에서 발견하고 수정한 결함

1. **타입만 붙이면 없는 증권으로도 연결됐다.** 보유종목 10개가 20개로 반환되는 사례를 잡았다. 실제 Equity/ETF 프로필로 타입을 해소하고 타입별 엣지 필터를 적용했다. 뉴스 언급·문서 종류·Actor·벤치마크도 실제 대상 조건을 사용한다.
2. **NULL FK가 가짜 관계 수에 포함됐다.** 부모가 모두 NULL인 Concept에서 관계 65,830개가 반환됐다. 모든 엣지 원본에 양끝 키 IS NOT NULL을 적용하고 전체 관계 수를 재검증했다.
3. **큰 금액이 Bolt에서 float로 바뀌었다.** `12345678901234567890.12345678`이 정밀도를 잃는 것을 확인했다. SQL numeric은 유지하며 그래프에는 명시적인 decimal_text 컬럼으로 전달한다. 소비자는 Decimal로 해석하고 계산은 SQL/Decimal 툴에서 한다.
4. **일봉의 전체 ID 문자열 정렬과 자기 조인이 30초를 넘었다.** 원본 복합 PK와 증권별 집계로 식별을 검사하고, 조회는 증권·날짜 조건을 함께 사용했다. 전수 속성 대조를 했다고 주장하지 않는다.

## 데이터·그래프 검증

- 회사와 주식 각각 2,766개, 발행 관계의 정방향·역방향 2,766쌍 일치.
- 참여 원본 159,689개를 보존하고 회사 77,056개·조직 881개 참여를 실제 Actor로 연결. 선택 대상의 15,609개 참여 기록은 역할·언급·ID까지 일치.
- 보유 기록 48,243개 보존. 10월 2일 방산 ETF 보유 구성종목 10개와 원비중을 한 그래프 질의로 대조.
- 공시·뉴스 31개와 사건 근거 141개의 ID·신뢰도 일치.
- 객체 23개 전체 속성의 표본 대조, 모든 매핑 링크의 선택 대상 정역방향 대조. 데이터가 빈 타입·관계는 별도 표시.
- SQL의 연결 가능한 관계에서 고아 참조 0건. 일봉 8,710,783건은 원본 PK·2,691개 증권별 집계·ID/값 표본으로 검사.
- 일봉 외 34개 관계의 **전체 그래프 엣지 수**가 SQL과 일치. 일봉 2개 관계는 SQL 분할 집계 및 그래프 표본 검증.
- 시험 전용 뷰의 값 변경이 재적재 없이 다음 그래프 질의에 반영됐다. 시험 후 23개 노드·36개 엣지의 전체 정의를 복원하고 시험 뷰를 삭제했다.

근거 파일: core-graph-verification.json, actor-graph-verification.json, holdings-graph-verification.json, documents-graph-verification.json, all-graph-verification.json, integrity.json, graph-edge-counts.json, redeployment.json. 모두 `output/ontology-views-puppygraph-20261005/`에 있다.

## 기본 질문과 F01

분석 기준을 **2026-10-05 09:00 KST까지 이용 가능한 자료**로 고정했다. 이 조건에서는 KODEX K-방산의 보유 기준일이 10월 1일로 선택됐다. 최신 날짜를 무조건 쓰지 않았다.

| 질문 범위 | 실제 결과 |
|---|---|
| 실제 보유 기업과 비중 | 10개 종목·발행회사·비중 일치 |
| 해당 종목의 가격 배경 | 9월 1일~10월 1일 관측 210개 일괄 조회, 값·거래량·가격 기준 일치 |
| 보유 기업의 공급자 역할 계약 사건 | 참여 기록 456개, 역할·유형·가용 시점 조건 일치 |
| 선택한 계약 사건의 뉴스 근거 | 사건 20개의 근거 20개 일치 |
| 한화에어로스페이스의 F01 자료 가용성 | 재무지표 124개 확인. 원가 구분·고정비/변동비·생산량 없음. 영업 레버리지 계산 보류 |

원본과 같은 조회 결과를 얻는 기본 능력 검증이다. 계약금액·제품 조건 검색, 현재 계약 상태 확정, 전체 ETF 전망 생성, LLM 에이전트의 자유 탐색은 이 결과에 포함하지 않는다.

목적에 기여한 사용은 8개 객체·7개 링크로 기록했다. 이를 객체 수로 나눠 커버리지 80%라고 부르지 않는다. 자세한 판정은 [coverage.md](coverage.md)에 있다.

## 효율 측정

동일 시점·조건·반환 열에서 SQL과 그래프의 결과가 일치한 뒤 각각 3회 측정했다. SSM 터널을 포함한 클라이언트 왕복 시간이며 부하 시험이나 SLA는 아니다.

| 범위 | 종목 / 행 | SQL 중앙값 | 그래프 중앙값 | 자료 요청당 호출 |
|---|---|---|---|---|
| 단일 종목 | 1 / 21 | 약 24ms | 약 353ms | 1회 |
| 지정 목록 | 3 / 63 | 약 26ms | 약 193ms | 1회 |
| ETF 전체 보유 종목 | 10 / 210 | 약 54ms | 약 354ms | 1회 |

종목마다 요청을 반복하지 않았다. 대상 집합 해소는 별도이며 PuppyGraph 내부에서 발생하는 SQL 개수까지 계측한 결과는 아니다. 이 가격 조회에서는 SQL이 더 빠르므로 그래프 도입의 성능 향상을 주장하지 않는다.

## 원본 부족과 남은 기능

- FinancialMetric 2건의 보고 문맥이 정확히 해소되지 않는다. `00118275`, 2025 Q4, bps_total_shares의 CFS/OFS 기록이며 임의 보고서를 붙이지 않았다.
- 거래소 분류 1,720개는 해당 종목코드의 instrument 자체가 DB에 없다. 분류 행은 보존하고 링크는 만들지 않았다.
- MarketIndex는 0개다. 테마·상위 개념·기사 대표본·사업부문 개념 등의 연결도 현재 원본이 비어 있다.
- 시가총액의 확정 금액/통화/범위, 사업부문 기간/분모, 일부 관측 시각은 정의대로 NULL이다.
- CalculatedFrom, 사건별 수치 특징 조건 검색, 신뢰할 수 있는 현재 사건 상태 산출, F01 원가 자료 확보는 후속이다.
- 80% 목적 적합 데이터 커버리지와 전체 에이전트 CQ 합격은 미확인이다.

## PR·환경·재현

순서대로 쌓은 draft PR: [#4 기본 회사/주식](https://github.com/junyoung7727/etf-research-agent/pull/4), [#5 사건 참여](https://github.com/junyoung7727/etf-research-agent/pull/5), [#6 보유 구성](https://github.com/junyoung7727/etf-research-agent/pull/6), [#7 문서](https://github.com/junyoung7727/etf-research-agent/pull/7), [#8 재무](https://github.com/junyoung7727/etf-research-agent/pull/8), [#9 시장 관측](https://github.com/junyoung7727/etf-research-agent/pull/9), [#10 대시보드·매핑](https://github.com/junyoung7727/etf-research-agent/pull/10). 병합하지 않았다. GitHub 자동 검사는 설정돼 있지 않다.

workbench가 작업 시작 때 Git 미추적 상태여서 #10에 기존 기준선과 이번 변경을 별도 커밋으로 담았다. 로컬 library.json, 시험 데이터, 비밀번호 및 다른 사용자 변경은 제외했다. 독립 체크아웃은 외부 온톨로지 경로·SQLite 스냅샷·이전 기준 모델 JSON을 준비해야 한다. 최초 스냅샷 부재로 15개가 실패했고, 준비 후 78개가 통과하면서 기준 JSON 부재 1개가 남았다. 해당 파일 준비 후 마지막 1개도 집중 재실행에서 통과했다. **총 79개 검사를 검증했고 건너뛴 검사는 없다.** 두 브라우저 검사도 통과했다. 별도의 GitHub CI 합격을 뜻하지 않는다.

PuppyGraph는 private Fargate 시험 태스크(2 vCPU / 16 GiB)로 실행 중이다. 공개 IP는 없으며 SSM bastion을 통해 접근한다. 운영 서비스·자동 복구·상시 운영 배포까지 완료한 상태는 아니다. 실행 리소스는 `puppy-task.json`, 재현 절차는 [graph-integration.md](../../apps/entity-workbench/docs/graph-integration.md)를 따른다.

고정 이미지: `puppygraph/puppygraph@sha256:8e362b158d8dde1ae9ed6df54f6751630af72a47d061bb2db42fa16547b368f7`. 참조한 공식 문서는 [그래프 매핑](https://docs.puppygraph.com/modeling/building-a-graph/), [PostgreSQL 타입](https://docs.puppygraph.com/connecting/connecting-to-postgresql/), [1.13.0 릴리스](https://docs.puppygraph.com/releases/)다. 최종 호환성은 위 실제 실행 결과로 판정했다.
