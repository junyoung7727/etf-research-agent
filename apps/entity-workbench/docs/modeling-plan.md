객체·모델 조회 화면: 사용자 정정에 따라 편집 기능은 제거. 저장된 정의 JSON, 실제 객체 JSON, 원본 출처를 조회한다. 기존 초안을 보존하고 모델 저장 API는 비활성화한다. 현재 SQLite 저장소를 운영 OMS로 표현하지 않는다.
2026-09-30: Graph DB 기반 논리 모델로 설계. 상단은 ObjectType 노드와 타입 간 edge인 schema graph, 하단은 labels·id·properties를 가진 instance JSON과 원본 행을 표시한다. 객체·속성·관계 라벨과 설명은 영어. label/displayName은 표시명이며 식별 키 또는 그래프 타입 labels와 구분한다. JSON export는 논리 그래프 교환 형식이며 특정 그래프 엔진 import 형식이 아니다. 중첩된 propertyDefinitions/sourceMapping은 정의 문서 구조로, 물리 그래프 DB에서 속성으로 그대로 저장할 수 있다고 가정하지 않는다. 실제 Graph DB는 미연결이며 기존 SQLite revision 저장소는 로컬 초안으로 유지한다.

2026-10-01: Source mapping 설계 확정
- SourceMapping 노드와 MAPPED_FROM 관계는 만들지 않는다. 객체 타입마다 하나의 sourceMapping 필드를 둔다.
- sourceMapping은 테이블 자체가 아니라 객체를 조립하는 조회 규칙이다. baseTable, filters, joins를 담는다.
- ID의 원본은 같은 타입 정의의 identity에, 속성별 원본은 propertyDefinitions[].source에 기록한다. 이 정보들이 함께 매핑을 구성하며 중복 저장하지 않는다.
- Company.sourceMapping.baseTable = company_profile. company_profile → actor → entity는 동일 객체를 조립하는 FK 조인 경로이며, Company → Equity의 발행 링크와 구분한다.
- 현재 modeler.js의 typeNode()와 JSON 내보내기는 이미 이 구조다. 별도 매핑 노드 제안은 폐기하고 이 결정을 다음 OMS 설계의 기준으로 삼는다.
- 논리 JSON의 내장 필드라는 뜻이다. 특정 그래프 DB의 중첩 속성 지원이나 물리 저장 방식은 아직 확정하지 않았다.


2026-10-01 최신 결정 — 원본 매핑 우선: models/*.yaml에 객체별 원본 PostgreSQL connection/schema/table/column 및 전체 FK 조립 명세를 먼저 기록한다. sourceMapping이 뷰를 참조한다는 이전 제안을 대체한다. 후속 SQL 뷰는 이 원본 명세에 맞춰 설계·검증하고 PuppyGraph는 완성된 뷰에 연결한다. yaml_models.py는 검증 및 로컬 미리보기 발행용이며 뷰 자동 생성기가 아니다.
