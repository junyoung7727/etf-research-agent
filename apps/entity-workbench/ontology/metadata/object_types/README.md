# Object source models

metadata/object_types/*.yaml은 24개 객체 타입·217개 속성·38개 링크 타입과 원본 PostgreSQL 매핑의 편집 정본이다. Palantir Foundry의 Object Type / Property / Link Type 개념을 따른다. 현재 YAML은 로컬 대시보드용 형식이며 Foundry에 직접 가져올 수 있는 공식 내보내기 형식은 아니다.

객체에는 API 이름·표시 이름·설명·기본키·표시 속성·개발 상태를 둔다. 속성의 모델 자료형과 원본 PostgreSQL 자료형을 구분한다. 복합 원본 키는 전체 구성값을 보존한 하나의 String 기본키로 노출한다. 별도의 해석 제한·에이전트 지침·semanticContract는 객체나 링크의 구성 요소로 두지 않는다.

하나의 링크 타입에 정방향과 역방향의 API 이름·표시 이름을 함께 정의한다. Company의 HasDisclosure와 Disclosure의 ForCompany, Company의 Issues와 Equity의 IssuedBy는 각각 하나의 링크 타입이다. 두 방향을 독립 링크로 중복 저장하지 않는다. 같은 객체에서 출발하는 모든 방향의 링크 API 이름은 서로 달라야 한다. 대상 타입이 다른 ForSecurity 등은 타입별 API 이름으로 구분한다.

객체·속성·링크의 status는 active / experimental / deprecated 중 하나다. 현재 로컬 초안은 experimental이다. sourceMapping과 mappingStatus는 데이터 연결의 명세·검토 상태이며 Ontology 개발 상태와 별개다. backing은 foreignKey / joinTable / object 구성을 나타내며 requiresPreparation은 원본 조인 결과를 객체 기본키로 변환한 데이터 준비가 필요하다는 뜻이다. Foundry 데이터셋 연결과 실제 인덱싱은 수행하지 않았다.

사건 참여는 Company/Organization → ParticipatesIn → SourceEvent 링크다. roleCode와 mentionedName은 링크 속성이고 event_argument_id는 링크 식별자다. 같은 대상과 사건 사이의 서로 다른 역할은 별도 링크로 보존한다. EventParticipation 객체는 두지 않는다. 원본의 NULL·미매칭 참조는 원본 행으로 보존하고 가짜 끝점이나 회사 변환으로 연결하지 않는다. 다른 링크의 sourceMapping.evidenceFields는 원본 매핑 참고자료이며 조회 가능한 Ontology 속성과 구분한다.

명칭·설명 기준은 [db-object-modeling](C:/Users/user/.codex/skills/db-object-modeling/SKILL.md)을 따른다. 객체는 대상과 한 건의 범위, 속성은 값·단위·시점, 링크는 대상의 역할을 영어로 설명한다. 이름만 반복하는 문장을 쓰지 않는다. 같은 원본 테이블에서도 업종 분류, 시장가치 관측, 상장정보 스냅샷은 서로 다른 객체로 표현한다. 수집·파싱·적재 상태와 실행 버전은 업무 속성에 포함하지 않는다. 공급계약은 별도 객체로 두지 않고 사건과 근거 문서로 다룬다.

- sourceMapping.connection의 aws_work는 논리 접속 참조다. 실제 호스트·database·비밀번호는 별도 설정에서 해소한다.
- schema/baseTable/joins/properties로 원본 경로를 기록한다. from과 alias는 조인 별칭이며 base는 기준 테이블이다.
- 복합 FK의 모든 열을 검사한다. LEFT JOIN으로 조립하며 ID 생성·중복 제거는 하지 않는다.
- formatVersion 2의 nullable은 모델의 NULL 계약이다. sourceDataType은 원본 PostgreSQL 자료형이며, sourceConstraints.nullable은 원본 DB의 NULL 허용 여부다. 조인 실패 가능성만으로 모델의 필수 속성을 선택 속성으로 바꾸지 않는다.
- sourceConstraints.primaryKey와 foreignKeys는 전체 구성 컬럼을 기록한다. 복합 FK는 해당 속성이 구성원이어도 전체 source/target 열을 표시한다. 일반 객체 링크나 코드 매핑이 존재한다는 이유로 DB FK가 있다고 표시하지 않는다.
- 원본 제약은 `../../../data/source-schema.json`의 2026-10-01 읽기 전용 카탈로그와 대조한다. 실시간 DB 제약 조회가 아니며 변경된 DB 스키마는 카탈로그를 다시 수집해 대조해야 한다.
- 복합 키는 identity.columns 순서를 유지한 JSON 문자열 배열로 조회 ID를 만든다. 날짜·판본을 제거하거나 새 ID를 발급하지 않는다.
- EventThread의 currentStage와 lastStateAt은 정의에 포함하되 현재 원본 계산의 의미가 달라 mappingStatus: needsCorrection이다. 미리보기에는 해당 값을 반환하지 않고 원본 행에서 원래 값을 확인하도록 한다. 사건 동일성·역할·상태·중복 정책은 별도 설계 문서에 기록한다.
- SQL 뷰·PuppyGraph 연결은 아직 미구현이다. 원본 명세를 근거로 SQL 뷰를 설계하고 결과를 검증한다. SQL 자동 생성기는 만들지 않는다.
- 공시에서 언급 회사·종목으로 가는 일반 링크는 모델에 두지 않는다. `HasDisclosure / ForCompany`는 공시 주체다. 계약 참여는 사건 참여 역할과 근거 문서로 확인한다. `NewsArticle.MentionsSecurity`는 종목별 기사 검색용이다. `Company.ParticipatesIn`은 참여 회사와 사건 계정의 N:N 관계이며 매핑 검토 상태다.
- FinancialReportSnapshot은 보고서 수집본이며 재수집을 정정 공시로 간주하지 않는다. reportCoverage는 원본 Q1/Q2/Q3/Q4를 Q1/H1/9M/FY로 정규화한다. 원본 키와 값은 보존한다. FinancialMetric의 HasReportingContext, ReportedIn, CalculatedFrom은 보고 문맥·직접 보고 출처·계산 입력을 구별하며 매핑 검토 상태다. calculationInputs는 원본 inputs를 보존하는 JSON 텍스트이며 실제 입력 참조 해소는 미구현이다.
- ReportedBusinessSegment의 shareCalculationMethod는 비중의 생성 방식을 설명한다. 파서의 품질 플래그와 채택 상태는 업무 속성에서 제외한다. UNRELIABLE은 계산 방식으로 노출하지 않으며 다른 방식이라고 신뢰도 검증 통과를 만들어내지 않는다. 기간·회계 범위·분모 속성은 원본 연결 대기 상태다.
- MarketCapitalization은 통화·대상 범위가 확인될 때까지 amount 매핑을 보류한다. SecurityListingSnapshot은 시점이 있는 상장정보를 보존한다. 분류의 snapshotDate와 collectedOn을 분리하며 확인되지 않은 유효일을 추정하지 않는다.
- IntradayInvestorFlow는 현재 KIS 원본 범위인 개별 주식의 외국인·기관 누계 추정치를 나타낸다. reportingSlotCode를 시각으로 변환하지 않으며 실제 기준시각 estimateAsOf는 미매핑이다. MarketIndex.regions도 근거 없는 UNKNOWN 배열 대신 미매핑 상태로 둔다.
- 원본 코드의 명확한 값 변환은 sourceMapping.properties의 valueMapping으로 정의한다. 매핑되지 않은 코드는 NULL이며 원본 행은 그대로 보존한다. 미매핑 속성을 관계의 의도한 연결 키로 정의할 수 있지만 값이나 실제 연결을 만들어내지는 않는다.
- DailyBar는 종목·거래일별 OHLCV와 거래대금을 포함하는 일봉이다. 거래량 volume은 주식의 주 수 또는 ETF의 좌 수(Long), 거래대금 turnoverValue는 거래 통화의 금액(Decimal)이다. 시가·고가·저가는 정제 데이터에 있지만 확인한 DB 스키마에는 없어 unmapped로 정의한다. 미매핑 속성은 원본 컬럼·DB 제약을 선언하지 않고 실제 값 미리보기에도 가짜 값을 만들지 않는다. 현재 로더는 거래대금·가격 기준·수익률에 NULL을 적재한다.

## 로컬 대시보드 발행

저장소 루트에서 `.cache/news-filter-benchmark/Scripts/python.exe -X utf8 apps/entity-workbench/scripts/publish_models.py` 실행.

YAML의 원본 컬럼·자료형·NULL·PK·전체 FK를 검사한 뒤 미리보기 형식으로 변환하여 models.sqlite3에 새 revision을 저장한다. `published-model.json`과 SQLite는 발행 사본이며 직접 편집하지 않는다. YAML 변경 후 이 명령을 실행하고 대시보드를 새로고침한다.

대시보드는 발행 시점의 YAML 원문을 객체별로 표시한다. 상단의 발행 버전·시각과 YAML 원본 일치 여부로 현재 파일이 발행되었는지 확인한다. 파일 내용이 바뀌면 다시 발행하고 화면의 `최신 확인`을 누른다. 일치 여부는 조회 시점의 전체 YAML 파일 내용과 발행 원문을 비교하며, 라이브 DB 데이터의 최신 여부를 뜻하지 않는다.

대시보드 sourceMapping은 원본 경로를 표시한다. 실제 값은 기존 로컬 스냅샷에서 조회하며 라이브 AWS 데이터가 아니다. SQL 뷰 명세와 운영 OMS는 후속 작업이다.

스냅샷에 없는 테이블도 모델 정의를 발행할 수 있다. 화면은 미수집 상태를 0행과 구분한다. DescribesEvent/InEventThread처럼 중간 테이블을 거치는 링크는 연결 경로와 전체 FK를 표시하며, source/target ID가 서로 같다는 조건으로 바꾸지 않는다. 코드 매핑·회사 참여·사건 동일성·기사 대표 선정의 검토 상태를 별도로 표시한다.

공식 기준: [Object metadata](https://www.palantir.com/docs/foundry/object-link-types/object-type-metadata), [Property metadata](https://www.palantir.com/docs/foundry/object-link-types/property-metadata), [Link metadata](https://www.palantir.com/docs/foundry/object-link-types/link-type-metadata), [양방향 이름과 object-backed links](https://www.palantir.com/docs/foundry/object-link-types/create-link-type).

2026-10-02 폴더 정리: 링크 본문은 이웃 `../link_types/`로 분리하고 객체에서는 `linkTypes`로 참조한다. 전체 객체·링크 의미는 이동 전과 동일하다.

운영 데이터 제외 결정과 상세 변경: [작업 기록](../../../../../output/ontology-domain-scope-20261002/review.md). 실행 ID 등은 원본 키·매핑에 필요한 경우에만 남기며 별도 업무 속성으로 노출하지 않는다.
