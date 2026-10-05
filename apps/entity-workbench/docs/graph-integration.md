# 그래프 매핑과 클라우드 검증 실행

현재 구현은 PostgreSQL 일반 VIEW를 PuppyGraph 1.13.0에서 직접 읽는다. 23개 노드 타입과 36개 엣지 타입을 등록하며, CalculatedFrom은 보류로 반환한다. 역방향 엣지를 복제하지 않는다. 인터페이스 조회는 실제 타입을 유지하는 단일 UNION ALL 질의로 변환한다.

## 입력과 실행 경계

`backend.puppygraph_schema.build_schema(catalog, object_names)`는 검토된 카탈로그에서 **접속 정보 없는** 그래프 정의와 보류/값 인코딩 보고를 만든다. 객체 정의 해시가 달라졌거나 미지원 값 인코딩이면 실패한다. 접속 비밀번호는 배포 시 메모리에서만 결합한다.

`backend.graph_queries.interface_traversal`은 Actor·Security·SourceDocument의 공통 관계를 구체 타입별 질의로 변환한다. 타입 있는 ID 목록은 최대 1,000개이며 ID와 필터 값은 파라미터로 전달한다. 같은 참여 기록의 역할과 키를 유지한다. 현재 이 함수는 페이지·날짜 범위를 포함한 고객용 조회 툴이 아니다. 큰 관측 조회는 별도 검증된 날짜·증권 조건을 사용한다.

금액 속성은 SQL에서 numeric이며, 그래프 응답에서는 decimal_text로 전송한다. 소비자는 `Decimal(value)`로 해석한다. float 변환·숫자 문자열의 대소 비교는 금지한다. 계산은 SQL 또는 정확한 Decimal 계산 툴에서 한다. 배열은 배열, NULL은 NULL로 유지한다.

## 재현 환경

- Python 패키지: boto3, psycopg2, neo4j 5.28.6, pytz. 기존 앱의 YAML 등 의존성도 필요하다.
- AWS의 dev RDS와 PuppyGraph pilot, SSM 원격 포트 포워딩이 필요하다. 현재 검증 도우미는 프로젝트의 work 프로필과 ap-northeast-2 dev 환경을 사용한다.
- DB 인증은 Secrets Manager 또는 SSM SecureString에서 읽는다. 저장된 결과·그래프 JSON에는 비밀번호가 없어야 한다.
- `EDGE_ONTOLOGY_ROOT`를 실제 라이브러리의 `src/libs/ontology/src/edge_ontology` 경로로 지정한다. 로컬 `data/library.json`은 환경 설정으로만 사용하며 PR에 포함하지 않는다.
- 실행 상태 파일은 `output/ontology-views-puppygraph-20261005/puppy-task.json`이다. cluster, task, credentialParameter 등 현재 시험 리소스 식별자를 담는다. 서비스가 재생성되면 이 파일의 task를 갱신해야 한다.

## 검사 순서

저장소 루트에서 아래를 순서대로 실행한다. 그래프 정의를 교체하므로 그래프 시험을 병렬 실행하지 않는다. DB 감사는 읽기 전용이다.

```powershell
python -m unittest discover -s apps/entity-workbench/tests -t apps/entity-workbench -p 'test_*.py'
python apps/entity-workbench/integration/audit_integrity.py
python apps/entity-workbench/integration/test_all_graph.py
python apps/entity-workbench/integration/test_null_edges.py
python apps/entity-workbench/integration/test_basic_cq.py
python apps/entity-workbench/integration/test_redeployment.py
```

재배포 시험은 격리된 deployment_probe 뷰만 만들고 변경한다. 같은 그래프 질의로 원본 값 변경이 보이는지 검사한 뒤 전체 모델로 복원하고 시험 뷰를 삭제한다. 원본 업무 테이블은 수정하지 않는다.

`test_all_graph`는 객체의 모든 속성 표본과 선택 대상의 모든 연결 기록을 비교한다. `test_null_edges`는 일봉 외 34개 관계의 전체 개수를 SQL과 비교한다. 일봉은 871만 건의 전체 ID 문자열 정렬 대신 원본 PK·증권별 집계·표본 ID/값/경로를 검사한다. 검증 범위를 전수 속성 대조로 확대 해석하면 안 된다.

`test_basic_cq`는 기본 조사 질문을 실행하는 통합 시험이다. LLM 에이전트의 자유 탐색이나 13개 전체 CQ를 통과시킨 시험은 아니다. 목적 적합 커버리지 80% 달성 여부도 별도다.
