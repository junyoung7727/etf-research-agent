# PuppyGraph 시험 도입·성능 측정 제안

작성: 2026-10-01. 상태: 제안. 설치·DB 변경·성능 측정은 아직 수행하지 않았다.

## 제안

PostgreSQL 객체 뷰를 PuppyGraph에서 복제 없이 그래프로 조회하는 작은 실험을 한다. 기존 5개 타입만 사용하며, 실제 결과와 성능을 확인한 뒤 도입 여부를 결정한다. 기존 v1 엔진은 사용하지 않는다.

```text
PostgreSQL 원본 → 객체별 SQL 뷰
                    ├─ SQL 조회 → 비교 기준
                    └─ PuppyGraph 외부 데이터소스 → Cypher 조회
                                                  ↓
                                        공통 조회 API → Agent / Dashboard

공통 객체 정의 → 타입·속성·링크·뷰 매핑
                    └─ PuppyGraph schema JSON 생성
```

PuppyGraph는 실제 데이터를 조회하는 엔진이다. OMS를 대체하는 것으로 취급하지 않는다. OMS의 물리 저장소 선택은 이번 실험과 분리한다.

## 우리 모델에 적용

| 객체 타입 | 제안 뷰 | 조립 원본 / ID |
|---|---|---|
| Company | ontology_view.company | company_profile + actor + entity / actor_id |
| Equity | ontology_view.equity | equity_profile + instrument + entity / instrument_id |
| Disclosure | ontology_view.disclosure | disclosure_document + document / document_id |
| EventParticipation | ontology_view.event_participation | event_argument / event_argument_id |
| SourceEvent | ontology_view.source_event | source_event / source_event_id |

- 조인 로직은 SQL 뷰에만 둔다. 복합 FK는 모든 열을 사용한다.
- 객체 정의의 sourceMapping은 뷰 이름·ID 컬럼·속성 컬럼 대응을 담는다. 별도 SourceMapping 노드는 만들지 않는다.
- 내부 ID와 코드 문자열을 보존한다. 그래프 드라이버의 정수 ID 직렬화도 확인한다.
- Property/Link 이름과 설명은 영어로 유지한다. 실제 회사명 등 원본 값은 번역하지 않는다.
- 현재의 JS 그래프 JSON은 표시용이다. 이를 그대로 PuppyGraph에 올리지 않고 공통 정의에서 해당 제품 스키마로 변환한다. UI와 PuppyGraph 양쪽에서 정의를 따로 편집하지 않는다.
- 이 구조는 이전의 OMS 내부 FK 조인 해석 제안을 대체한다. 기존 미리보기 조인 코드는 새 뷰와 결과를 대조하는 데 활용한다.

링크는 아래 조건으로 정의하고, 필요하면 source_id·target_id·안정적인 edge_id를 반환하는 일반 SQL 뷰로 노출한다. 관계 키는 원본 기록의 키로 결정하며 임의 순번을 쓰지 않는다.

| 링크 | 연결 조건 |
|---|---|
| Company → Issues → Equity | company.id = equity.issuer_id |
| Company → FiledDisclosure → Disclosure | company.id = disclosure.issuer_id |
| Equity → EquityParticipation → EventParticipation | equity.id = event_participation.entity_id |
| SourceEvent → HasParticipation → EventParticipation | source_event.id = event_participation.event_id |
| Company → DirectParticipation → EventParticipation | company.id = event_participation.entity_id |

직접 회사 참조는 기존 스냅샷에서 0건이었다. COMPANY_ENTITY 분류를 회사 ID로 강제 변환하지 않는다. NULL 대상 기록은 참여 노드로 보존하되 존재하지 않는 대상 엣지를 만들지 않는다. 공급망 추정과 새로운 객체 타입은 범위 밖이다.

## 실행 순서와 완료 기준

| 순서 | 작업 | 완료 기준 |
|---|---|---|
| 1 | 고정 PostgreSQL 시험 데이터와 객체·관계 뷰 준비 | ID 중복·행 증가·조인 누락을 집계하고 기존 미리보기 결과와 대조 |
| 2 | 같은 네트워크의 별도 컨테이너에 PuppyGraph 실행, 조회 전용 계정 연결 | 버전·에디션·라이선스·자원 기록. 일반 뷰 조회와 그래프 매핑 성공 |
| 3 | Local Replication/localTable 없이 external datasource로 매핑 | 5개 타입과 링크의 ID·건수·속성값 일치. 누락 대상은 별도 집계 |
| 4 | SQL 대 Cypher 측정 | 아래 결과표와 실행 계획 저장, 통과/보류 판정 |
| 5 | 통과 시 공통 API에 PuppyGraph 조회 구현 추가 | 대시보드에서 회사 → 주식 → 참여 기록 → 이벤트와 원본 행 대조 |

기존 AWS 조회 계정은 SELECT에만 사용한다. 뷰 DDL은 시험 환경에 적용한다. 일반 뷰 지원·권한·타입 호환에 실패하면 원인을 기록하고 중단하며, 몰래 테이블 복제로 바꿔 측정하지 않는다. 시험용 고정 데이터는 공정한 비교용이며 운영 그래프 동기화 도입을 뜻하지 않는다.

## 성능 측정

| 쿼리 | 목적 |
|---|---|
| Q1: Company ID로 속성 조회 | 단순 조회 비용 |
| Q2: 회사의 발행 주식 조회 | 1단계 관계 조회 |
| Q3: 회사 → 주식 → 참여 기록 → 이벤트 | 현재 모델의 핵심 3단계 조회. 역할·날짜 필터 포함 |
| Q4: 두 회사가 함께 연결된 이벤트 | 분기된 경로의 교집합. 같은 이벤트 참여가 거래 관계임을 뜻하지 않음 |
| Q5: 허용된 링크만 1~4단계 경로 탐색 | 가변 경로 조회. 동일 노드 재방문 금지, 동일 경로 반환 의미로 비교 |

현재 관계는 짧고 구조가 제한적이므로 이 실험으로 공급망의 깊은 재귀 탐색 성능까지 입증하지 않는다. 그 요구가 생기면 별도 측정한다.

측정 방법:

1. 같은 고정 데이터·시점·필터·방향·NULL 처리·반환 컬럼·중복/경로 의미를 사용한다. 결과 ID/경로와 속성을 먼저 비교한다. LIMIT로 한쪽의 작업량만 줄이지 않는다.
2. 연결 수가 0/적음/많음인 회사에서 총 30개 ID를 고정한다. Q4는 고정 회사 쌍, Q5는 같은 깊이·허용 링크를 사용한다.
3. 각 파라미터의 첫 실행을 따로 기록한다. 그 뒤 3회 준비 실행, 10회 측정한다. 첫 실행을 완전한 cold-cache라고 부르지 않는다. 원본 DB 캐시는 강제로 비우지 않는다.
4. SQL/Cypher 실행 순서를 교대하고 동일 클라이언트 위치에서 결과 수신 완료까지 측정한다. 동시성 1과 5를 따로 실행한다. 쿼리 제한은 양쪽 모두 30초로 맞추고 timeout도 결과에 포함한다.
5. p50/p95, 오류·timeout, 결과 건수, PostgreSQL CPU·읽기 I/O, PuppyGraph CPU·메모리, 가능한 전송량을 기록한다. PostgreSQL은 EXPLAIN ANALYZE/BUFFERS, PuppyGraph는 EXPLAIN/PROFILE을 별도 진단 실행에서 저장한다. 진단 실행 시간은 일반 지연시간 표에 섞지 않는다.
6. SQL 기준선도 적절한 인덱스·통계를 갖춘다. DB 상태와 추가 엔진 자원·비용을 함께 적는다. 메트릭 권한이 없으면 미측정으로 표시하며 성능 도입 판정을 유보한다.

기존 로컬 스냅샷은 회사 2,766개, 주식 2,766개, 공시 226개, 최근 이벤트 1,500개·참여 기록 4,021개였다. 이는 정확성 점검용 작은 표본이다. 성능 판정에는 허용된 전체 시험 데이터의 건수·관계 분포를 새로 기록한다. 일부 데이터만 확보되면 결과를 예비 측정으로 한정한다.

## 도입 판정 — 실험 전 고정할 제안 기준

- 필수: 모든 비교 쿼리 결과 일치, 복제 모드 비활성, 원본 변경 후 재조회 반영 확인. 불일치 원인을 해결하지 못하면 도입 보류.
- 성능 채택: Q3~Q5 중 실제 사용할 2개 이상에서 warm p95가 SQL의 50% 이하이고 2초 이하. 같은 동시성에서 PostgreSQL CPU·읽기 I/O 증가율 각각 20% 이내, 측정 오류·timeout 0건. 이 수치는 제품 보장이 아니라 우리 시험의 제안 목표다.
- Q1~Q2가 느리면 기존 SQL 경로를 유지한다. 조회 종류별 구현 선택은 코드로 고정하고 LLM에 맡기지 않는다.
- 성능 기준에 미달하면 속도 개선을 이유로 도입하지 않는다. 그래프 질의 작성 편의만으로 채택할지는 별도 결정한다.
- 로컬 복제를 켜야 통과하면 '복제 없는 도입 성공'으로 보고하지 않는다. 별도 실험으로 분리한다.

최종 산출물: 뷰 SQL, 공통 정의→제품 스키마 매핑, SQL/Cypher 쿼리 쌍, 원시 측정 CSV, 실행 계획, 1쪽 도입/보류 결과. 기존 SQL 경로를 유지해 시험 엔진을 제거해도 조회가 가능하게 한다.

## 공식 근거

- [PostgreSQL 직접 조회 예제](https://docs.puppygraph.com/getting-started/querying-postgresql-data-as-a-graph/): 별도 엔진으로 기존 PostgreSQL 데이터를 조회.
- [Graph Modeling](https://docs.puppygraph.com/modeling/): 테이블을 노드·엣지로 매핑하는 JSON 스키마.
- [Data Sources and Local Tables](https://docs.puppygraph.com/modeling/data-sources/): 외부 조회와 로컬 저장 모드를 구분.
- [Releases](https://docs.puppygraph.com/releases/): EXPLAIN/PROFILE, 경로 계획·PostgreSQL pushdown 관련 구현 기록. 실제 적용은 시험에 고정한 버전으로 확인.


2026-10-01 최신 결정 — 원본 매핑 우선: models/*.yaml에 객체별 원본 PostgreSQL connection/schema/table/column 및 전체 FK 조립 명세를 먼저 기록한다. sourceMapping이 뷰를 참조한다는 이전 제안을 대체한다. 후속 SQL 뷰는 이 원본 명세에 맞춰 설계·검증하고 PuppyGraph는 완성된 뷰에 연결한다. yaml_models.py는 검증 및 로컬 미리보기 발행용이며 뷰 자동 생성기가 아니다.
