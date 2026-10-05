# Entity Atlas — 엔티티 검증 대시보드

## 개발 구조

```text
entity-workbench/
  ontology/     # 이식 가능한 객체·링크 정의와 순수 정의 로더
  backend/      # HTTP 서버, 스냅샷 조회, 정의 검증·발행, 로컬 저장
  frontend/     # entities / objects / value_types / vendor
  data/         # 원본 스키마 카탈로그
  tests/        # Python·브라우저·그래프 배치 검증
  scripts/      # 모델 발행 진입점
  docs/         # 설계·도입 계획
  paths.py      # 앱 경로와 외부 라이브러리 위치 설정
  workbench.py  # 기존 실행 명령을 유지하는 서버 진입점
```

기본 조회는 **라이브러리 + 대시보드 미반영 초안**을 합친다. **라이브러리에 반영** 버튼은 검증한 정의를 라이브러리 파일로 옮기고 초안을 제거한다. Git 커밋은 만들지 않는다. 저장 경계와 검증은 [정의 저장소 설계](docs/definition-sources.md)에 있다.

새 모델 발행: `.cache/news-filter-benchmark/Scripts/python.exe -X utf8 apps/entity-workbench/scripts/publish_models.py`.

`data/library.json`에 기본 라이브러리 경로를 지정한다. 현재는 `D:/Github/edge-ontology-layout/src/libs/ontology/src/edge_ontology`이며 `EDGE_ONTOLOGY_ROOT`가 우선한다. 화면에 실제 반영 경로를 표시한다. 서버 주소와 실행 명령은 그대로다.

## SQL 뷰 설계

주소: http://127.0.0.1:5186/view-design — `/modeler`의 **SQL 뷰 설계** 링크와 객체 상세에서 이동한다. 객체 뷰 23개와 관계 뷰 37개의 행 단위·ID·컬럼·원본 조인·미결 사항을 조회한다. 실제 DB 뷰 생성과 PuppyGraph 연결은 수행하지 않는다. 설계 원본과 검증 범위는 [뷰 설계 문서](docs/view-design.md)에 있다.

## Value Types · 값과 스레드 조건 관리

같은 관리 영역의 **Interfaces** 탭([인터페이스 관리](http://127.0.0.1:5186/interfaces))에서 Actor·Security·SourceDocument의 공통 속성·관계와 객체별 구현 매핑을 관리한다. 계약 검증 후 로컬 초안을 저장하고 별도 버튼으로 라이브러리에 반영한다. 인터페이스 정의·검증·저장 경계는 [인터페이스 관리 문서](docs/interfaces.md)를 따른다.

주소: http://127.0.0.1:5186/value-types — `/modeler`의 **Value Types** 링크로 이동한다.

- 왼쪽은 **Value Type 목록**, 가운데는 선택 타입의 허용값 검색·분류와 이벤트 연결조건 그래프, 오른쪽은 설명·규칙 편집과 JSON이다.
- 초기 목록은 EDGE의 명시적 리소스에서 가져온 String enum 8종이다: EventTypeCode(53), EventFamilyCode(7), EventPredicateCode(81), EventRoleCode(87), LifecycleModelCode(20), EventStageCode(38), EventNoveltyStatus(5), MissingIdentityPolicy(1). 수치는 2026-10-02 로컬 리소스 기준이며 실제 화면은 원본에서 계산한다. 임의 DB 관측값을 허용값으로 추정하지 않는다.
- Value Type과 값을 추가하고 설명·분류를 수정할 수 있다. 이벤트 값은 필수 식별 조건·보조 조건·결측 정책도 편집한다. 필수 조건의 순서는 식별 키 순서이므로 유지한다. 원본 코드를 삭제하거나 이름을 바꾸는 기능은 제공하지 않는다.
- **변경사항 저장**은 `output/entity-workbench/value-types.sqlite3`에 현재 미반영 변경분만 기록한다. **라이브러리에 반영**은 해당 원본 YAML을 갱신하고 확인 후 초안을 비운다. 두 동작 모두 Git 커밋·운영 배포·실제 이벤트 재연결을 수행하지 않는다. enum 주석/신규 정의는 라이브러리 `metadata/value_types/enum_annotations.yaml`에 원본에 없는 정보만 저장한다. 코드만 있고 역할·속성 스키마가 없는 새 이벤트는 반영을 거절하고 초안에 보존한다.
- 원본 해시 또는 저장 버전이 달라지면 저장을 거절하고 초안을 보존한다. 원본 비교와 JSON 내보내기를 제공하며 원본 변경의 자동 병합은 하지 않는다. v1 엔진을 호출하지 않는다.
- 현재 로컬 `assemble_events._thread_key`가 사용하는 필수 역할과 계약에만 있는 보조 조건을 구분해 표시한다. 운영 배포 상태를 조회한 것은 아니다.

검증: `python -m unittest discover -s apps/entity-workbench/tests -t apps/entity-workbench -p test_value_types.py`, `node apps/entity-workbench/tests/value-types-smoke.cjs`. 브라우저 검증은 임시 서버와 별도 임시 DB에서 실행하므로 사용자 초안을 수정하지 않는다. 결과는 `output/entity-workbench/value-types-verification.json`과 `value-types-*.png`에 저장한다.

기존 EDGE의 `entity` 체계를 타입부터 실제 DB 행까지 탐색하고, FK·기업 코드·기존 별칭을 대조하는 로컬 작업 화면이다. 원본 DB와 운영 매핑은 변경하지 않는다. 검증 판정은 별도의 SQLite 이력에 저장한다.

[엔티티 매핑 경로 아키텍처와 코드 지도](<C:/Users/user/Documents/Obsidian Vault/Project/ETF ORCA/온톨로지 설계/엔티티 매핑 경로 아키텍처와 코드 지도.md>)에서 마스터 생성·뉴스/공시 해소·분석 소비 경로와 선행 문서를 확인할 수 있다.

## 실행

프로젝트 루트에서:

```powershell
.cache/news-filter-benchmark/Scripts/python.exe -X utf8 apps/entity-workbench/workbench.py --capture
.cache/news-filter-benchmark/Scripts/python.exe -X utf8 apps/entity-workbench/workbench.py
```

주소: http://127.0.0.1:5186 — 최초 스냅샷 수집 후에는 AWS 연결 없이도 조회할 수 있다. 화면의 **DB 스냅샷 갱신**은 새 읽기 전용 수집을 수행한다. 실패하면 이전 스냅샷을 보존한다. 서버는 루프백 주소에만 바인딩하며 로컬 쓰기 요청에 토큰을 요구한다.

AWS 연결은 기존 `apps/news-research/source.py`를 재사용한다. `work` 프로필·Session Manager 플러그인·boto3·psycopg2가 필요하다. 자격 증명은 브라우저나 스냅샷에 저장하지 않는다. 기존 어댑터의 `agent_ro`, read-only, repeatable-read 검증 및 종료 처리를 따른다.

## 사용하는 법

1. **구조:** Entity → Actor / Instrument / Concept와 대표 프로파일을 본다. 점선은 분류 관계다.
2. **타입:** 노드를 클릭하거나 확대하면 화면 크기와 확대 수준에 따라 펼쳐지는 수가 연속적으로 늘어난다. 최대 180% 또는 **전체 펼치기**에서 해당 타입의 모든 엔티티가 캔버스에 배치된다. Company는 회사만, Actor는 기관 등을 포함한 모든 행위자다. 고정 2,400개 제한 없이 스냅샷의 실제 전체 수를 사용한다.
3. **실제 행:** 엔티티를 선택하면 entity·actor·company_profile·instrument·equity_profile 등의 실제 행과 FK를 표시한다. 실선은 원본 DB 제약조건이다. 복합 FK는 전체 열을 함께 비교한다.
4. **행 대조:** 노드를 누르면 오른쪽 테이블을 해당 행으로 필터링한다. 연결선을 누르거나 행 상세의 FK 값을 누르면 양쪽 원본 행을 함께 표시한다.
5. **검증:** 확인 / 불일치 / 보류와 메모를 남긴다. 판정은 연결 키와 양쪽 행의 해시에 묶이며 과거 판정을 덮어쓰지 않는다. 이후 해당 연결을 열 때 원본 해시가 달라졌으면 재검증 메시지가 나온다.
6. **기업 문서:** 기업 또는 주식을 선택한 뒤 버튼을 누른다. 직접 공시와 기존 종목 연결의 기업 투영을 구분한다. 수집 범위 내 최대 100행이다.
7. **외부 코드·별칭:** 02 단계를 누르면 DART 코드 테이블과 선행 엔지니어의 별칭 사전을 확인한다. 별칭은 DB 테이블이 아닌 EDGE 코드에서 가져온 자료임을 표시한다.

슬라이더·확대 버튼으로 구조에서 타입 목록으로 전환하고, 타입 목록의 펼침 수를 늘린다. 개별 노드를 선택하면 실제 행·FK로 들어간다. 목록의 최대 확대가 자동으로 단일 행 보기로 바뀌지는 않는다. 목록에서는 휠/Shift+휠·스크롤바·드래그·방향 버튼으로 가로세로 이동하며 **Ctrl+휠**로 확대한다. 처음/마지막 버튼으로 목록 양끝에 접근한다.

타입 목록은 기본으로 사전 배치를 켠다. A 한 행, B 다음 행, ㄱ 다음 행처럼 글자별로 아래로 내려가며, 같은 글자의 카드는 한 행 안에서 이름순으로 가로 배치한다. 사전 배치 버튼을 끄면 일반 격자로 돌아간다. 화면 밖 노드는 제거한 것이 아니라 좌표와 ID를 유지하고, 보이는 구간만 SVG로 그린다. 따라서 수천 개의 DOM을 한꺼번에 만들지 않으면서 마지막 엔티티까지 탐색할 수 있다. 화면 맞춤은 타입 목록에서 카드 크기를 유지한 채 처음 위치로 돌아가고, 구조/실제 행 보기에서는 그래프 전체를 화면에 맞춘다. 가운데 경계선으로 패널 너비를 조절하며 좁은 화면은 상하 배치로 전환한다. 분류 점선은 진한 녹색으로 표시한다.

## 범위와 정확성

- 현재 스키마의 지정된 17개 테이블을 수집한다. 원본 테이블과 DB 전체 행 수, 수집 행 수, 촬영 시각을 표시한다.
- 회사·증권·개념 명부와 공시 사실은 전체 수집한다. 문서는 최근 3,000개 + 공시 문서, 사건은 최근 1,500개와 그 인자를 수집한다. 편입 내역은 ETF별 최신 기준일만 수집한다. 원본에는 더 많은 뉴스·사건·과거 편입이 있다.
- 화면은 직접 SQL을 매 클릭마다 실행하는 실시간 DB 콘솔이 아니라 **일관된 DB 스냅샷의 원본 행을 대조하는 화면**이다. 해당 시점 이후의 변경은 갱신해야 반영된다.
- FK의 존재는 두 기업의 동일성 또는 경제적 영향에 대한 증거와 다르다. 기존 뉴스 instrument 연결을 confirmed company identity로 승격하지 않는다.
- 행 검색은 대소문자 처리 등 SQLite 기본 LIKE 의미를 사용한다. `%`, `_`는 와일드카드가 아니라 문자로 검색한다. 정렬은 한 열씩, 페이지 크기는 40행이다. numeric 값은 원본 문자열로 보존하고 Decimal 비교로 정렬한다.
- 한 번 클릭은 해당 카드의 상세로 진입한다. 이름 카드 더블클릭은 기업·증권 정체성 행들의 직접 FK를 양방향으로 모두 확장한다. 실제 행 카드 더블클릭은 그 행의 직접 FK를 추가 확장한다. DB에 선언된 FK와 현재 스냅샷을 기준으로 하며, 여러 홉을 무제한 자동 재귀 탐색하거나 코드상 추론 관계를 추가하지 않는다. 부분 수집 테이블과 스냅샷 밖 대상 수는 그래프 위에 표시한다.
- ③은 현재 사건 인자와 연결을 **검토하는 기능**이다. 2026-10-03에 사건의 Equity 참여 참조를 발행 Actor로 전환하고 뉴스·공시 writer에 적용했다([PR #1106](https://github.com/alphaeveryday/edge/pull/1106)). 사건·참여·묶음 ID와 역할·근거·이력은 보존했다. 사건 동일성 추정의 모든 문제를 해결한 것은 아니다. ④의 우선주·비상장·이력 신규 모델도 아직 적용하지 않았다. 검증 범위는 [CQ 툴 체크포인트](../../tasks/cq-tools/todo.md)에 기록한다.
- 검증 결과는 단일 사용자 로컬 기록이다. 사용자 계정별 승인·운영 DB 수정·팀 동시 편집 기능은 포함하지 않는다.

## 저장 위치

`output/entity-workbench/snapshot.sqlite3`에는 원본 스냅샷과 스키마 메타데이터가, `reviews.sqlite3`에는 append-only 검증 기록이 저장된다. 새 스냅샷은 완전 수집·연결 정리·로컬 커밋 후 파일을 교체한다. 갱신 중에는 이전 파일을 계속 조회한다. 별칭은 로컬 EDGE 소스에서 읽으며 해시를 메타데이터에 보존한다.

검증 기록 내보내기는 JSON이다. 외부 코드 매핑·별칭 테이블을 운영 DB에 신설하거나 기존 PK/FK를 변경하지 않는다.

## 검증

```powershell
.cache/news-filter-benchmark/Scripts/python.exe -X utf8 -m unittest discover -s apps/entity-workbench/tests -t apps/entity-workbench -p test_workbench.py
node --check apps/entity-workbench/app.js
node --test apps/entity-workbench/tests/graph-layout.test.mjs
node apps/entity-workbench/tests/smoke.cjs
```

브라우저 검증은 실행 중인 로컬 서버와 기존 `apps/edge/node_modules/@playwright/test` 설치를 사용한다. 검증용 판정만 별도 메모로 생성하고 종료 시 해당 판정을 제거한다. 사용자 판정은 건드리지 않는다.

단위 검증: 기업/증권 검색 구분, SQL 식별자 제한, 검증 이력·근거 버전, 복합 FK의 오연결 방지, 큰 수의 정확한 보존·정렬.

전체 목록·배치 검증: 2,400개 API 반환에 페이지 제한이 적용되지 않음, 회사/증권 분리, 확대에 따른 단조 증가와 최대 전체 펼침, 모든 노드 좌표의 유일성, 마지막 노드 접근, 캔버스 전 구간 이동 시 누락 없는 도달 가능성. 브라우저에서는 실제 회사 2,766개 펼침·사전 배치 전환과 가로·세로 이동·마지막 기업 선택을 확인한다.

브라우저 검증: 구조/타입/행 전환, 기업 검색, FK 비교, 배치 방향, 기업 문서, 별칭, 저장 후 새로고침 보존, 영문 포함 코드 검색, 정렬·페이지, 토큰 보호, 좁은 화면. 결과와 화면 캡처는 `output/entity-workbench/`에 저장한다.

## 이름 인덱스와 화면 이동

타입 목록은 숫자 → A–Z → ㄱ–ㅎ → 기타 순으로 묶고 각 구간을 한국어 자연 정렬한다. 동일한 이름도 ID별로 보존한다. 상단 글자 인덱스는 해당 구간 첫 행으로 이동하며, 아직 펼쳐지지 않은 구간이면 전체를 펼친다. 이름을 알고 있다면 왼쪽 검색창을 이용한다.

그래프의 오른쪽·하단 스크롤바는 숨기되 휠 스크롤과 방향 버튼은 유지한다. 배경 왼쪽 드래그 또는 노드 위에서도 가능한 휠 버튼 누른 채 드래그로 이동한다. Ctrl+휠은 확대한다. 관계 이름은 굵고 진하게 표시하며 축소 상태에서도 최소 12px로 유지한다.

행 대조 상단에는 현재 `public.테이블명`, 개별 행과 비교 양쪽에는 원본 테이블과 ID 값을 표시한다. 코드 별칭은 DB 행과 구분해 출처를 표시한다.

큰 화면에서는 그래프와 행 대조를 약 70:30 비율로 배치하며, 가운데 경계로 조절할 수 있다. 더블클릭은 단일 클릭과 충돌하지 않도록 구분하며 키보드에서는 Shift+Enter로 연결을 확장한다.

사전 배치는 초기 확대율부터 전체 항목의 좌표와 스크롤 영역을 확보한다. 확대는 카드 크기를 바꾸며 글자 구간을 제거하지 않는다. 일반 배치만 확대에 따라 표시 개수를 늘린다. 초기 100%에서 인덱스 클릭이나 전체 펼치기 없이 휠로 ㅎ 구간까지 내려가는 회귀 검증을 포함한다.

## 객체·모델 조회 화면

2026-10-02: `/modeler`의 현재 정의는 24개 객체·217개 속성·38개 링크 타입이다. Palantir의 객체·속성·링크 메타데이터를 따라 API 이름, 표시 이름, 기본키, 표시 속성, 개발 상태와 링크의 양방향 이름을 보여 준다. 업종 분류·시장가치·상장정보를 구별하고, 보고된 사업부문·보고서 수집본의 한 건 단위를 이름에 표시한다. 자동 배치와 객체 선택 목록으로 전체 구조를 탐색하고, 우측 속성을 펼치면 모델 NULL 계약·원본 NOT NULL·PK·전체 FK 컬럼을 볼 수 있다. 같은 사건을 추적하는 EventThread와 진행 상태 속성은 유지하며 데이터 결함과 미수집 원본은 별도로 표시한다. YAML 형식과 발행 절차는 [object_types/README.md](ontology/metadata/object_types/README.md)를 따른다.

그래프는 로컬 ELK 0.12.0으로 카드 위치·직각 연결선·관계 이름의 공간을 함께 계산한다. 별도 접점을 사용해 왕복 관계와 같은 두 타입 사이의 여러 링크를 구분한다. 카드에는 타입·원본 테이블·속성 수를 요약하고, 속성 전체는 오른쪽에서 확인한다. 전체 그래프의 모든 선 교차를 없애는 것은 보장하지 않는다.

- **자동 배치:** 현재 범위의 관계를 기준으로 다시 정렬하고 화면에 맞춘다.
- **카드 한 번 클릭:** 해당 객체의 정의를 확인하고 직접 관계를 강조한다.
- **더블클릭 / Shift+Enter / 연결 보기 / 객체 찾기:** 선택 객체의 들어오는·나가는 직접 관계만 별도로 배치한다. 화면 상단에 전체 대비 표시 개수를 알린다.
- **전체 보기:** 24개 객체 타입·38개 링크 타입을 다시 모두 표시한다. 하나의 링크를 누르면 양방향 이름과 API를 함께 볼 수 있다. 고립된 타입과 자기 자신으로 돌아오는 링크도 유지한다.
- **카드 드래그:** 놓은 위치를 배치 힌트로 사용해 주변 카드와 연결선을 다시 정렬한다. 저장된 객체 모델을 변경하지 않는다.

배치 검증: `node --test apps/entity-workbench/tests/model-layout.test.mjs`, `node apps/entity-workbench/tests/model-layout-smoke.cjs` (5186 서버 필요). 순환·역방향·다중 링크, 실제 모델의 카드 관통·카드 겹침·관계 이름 겹침, 더블클릭, 수동 이동 후 경로 재계산, 전체 보기 복원, 휠 확대·이동과 저장 모델 불변을 검사한다. 근거는 `output/entity-workbench/layout-verification.json`과 `layout-*.png`에 있다.

추가 검증: `python -m unittest discover -s apps/entity-workbench/tests -t apps/entity-workbench -p 'test_*.py'`, `node apps/entity-workbench/tests/design-modeler-smoke.cjs` (5186 서버 필요). JSON 검증 결과와 화면 캡처는 `output/entity-workbench/design-*`에 저장된다.

/modeler는 저장된 객체·관계 그래프와 JSON을 읽기 전용으로 표시한다.
객체 선택 시 저장 정의 JSON, 객체 데이터 조회 시 스냅샷의 객체 JSON과 원본 행을 표시한다.
현재 모델 저장소는 SQLite models.sqlite3이며 운영 OMS나 팔란티어 OMS에 연결된 것이 아니다.
편집·추가·삭제·저장 UI를 제거했고 저장 POST API도 405로 비활성화했다. 기존 초안은 보존한다.
빈 저장소는 빈 상태로 표시한다. 예시를 자동 생성하지 않는다. 카드 이동은 화면에만 적용한다.
v1 엔진과 회사 식별 규칙을 사용하지 않으며 뉴스 모델도 자동 가져오지 않는다.
검증: node apps/entity-workbench/tests/modeler-smoke.cjs
