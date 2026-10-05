# 인터페이스 관리

목표: Actor, Security, SourceDocument의 공통 계약과 객체별 구현 매핑을 라이브러리에 반영하고 Value Types와 같은 관리 영역에서 편집·검증·초안 저장·라이브러리 반영을 제공한다. 객체 데이터 조회 엔진이나 운영 DB를 변경하는 작업은 아니다.

정본은 `metadata/interface_types/<Name>.yaml`이다. 각 정의의 `implementations`가 구현 선언과 매핑의 단일 정본이며, 로더가 각 객체의 `implementedInterfaces`를 계산한다. 객체 YAML에 같은 선언을 중복 저장하지 않는다. 인터페이스별 공통 속성의 타입·NULL 정책, 관계의 대상·개수·필수 여부와 정방향/역방향 매핑을 명시한다. ID 매핑은 구현 객체의 PK를 보존한다.

작업 단위:

1. 공통 계약 검증기와 세 초기 정의 작성. 누락 속성·타입/NULL 불일치·잘못된 관계 방향/대상/개수·PK 대체를 거부한다.
2. 기존 객체 로더와 모델 화면에 구현 정보를 연결한다.
3. 버전·원본 해시 검사와 파일 롤백을 갖춘 초안 저장/반영 API를 만든다.
4. Value Types 옆 Interfaces 화면에서 공통 속성·관계·구현 매핑을 편집한다.
5. 임시 라이브러리·임시 SQLite로 저장·재조회·충돌·반영·실패 롤백을 검증한다. 사용자 초안을 테스트에 사용하지 않는다.
6. 실제 브라우저에서 세 계약, 편집, 저장, 반영, 잘못된 매핑 거부, 모바일 화면과 기존 Value Types 동작을 검증한다.

완료 조건: 세 인터페이스의 모든 구현이 실제 객체·관계 정의로 해소되고, 잘못된 계약을 저장/반영하지 못하며, 라이브러리 반영 후 객체 모델에서 구현 선언을 조회할 수 있어야 한다. 인터페이스 계약 충족은 실제 데이터가 존재한다는 보장이 아니다. 원본과 함께 데이터 채움 상태를 별도로 확인한다.

## 반영한 계약

| 인터페이스 | 구현 객체 | 공통 속성 | 공통 관계 |
|---|---|---|---|
| Actor | Company, Organization | id, name, countryCode | participatesIn → SourceEvent |
| Security | Equity, ETF | id, name, ticker, marketCode, currencyCode | dailyBars → DailyBar, dailyInvestorFlows → DailyInvestorFlow, heldIn → ETFHolding |
| SourceDocument | NewsArticle, Disclosure | id, title, publishedAt, availableAt, sourceUri | describesEvents → SourceEvent |

Security의 공통 관계는 해당 관측·보유 기록에서 출발하는 기존 링크의 역방향이다. 회사의 재무정보와 ETF의 NAV는 공통 계약에 추가하지 않았다. MarketIndex는 Security 구현 객체가 아니며, FinancialReportSnapshot은 SourceDocument 구현 객체가 아니다. 속성의 NULL 허용은 두 구현 객체의 현재 계약을 모두 충족하도록 설정했다.

## 관리와 저장

- `/value-types`와 `/interfaces`는 같은 관리 내비게이션을 공유한다. 객체 상세의 Implements에서도 해당 인터페이스로 이동한다.
- 인터페이스 추가·삭제, 공통 속성/관계 추가·수정·삭제, 구현 객체 추가·해제, 속성 및 정방향/역방향 관계 매핑을 편집할 수 있다. 이름은 정의의 식별자이므로 생성 후 직접 바꾸지 않는다.
- `GET /api/interfaces`는 원본·초안·현재 객체/관계 정의·검증 결과를 반환한다.
- `POST /api/interfaces`는 검증된 초안을 `output/entity-workbench/interfaces.sqlite3`에 저장한다. `/api/interfaces/apply`는 검증 후 인터페이스 YAML만 변경하고 초안을 비운다. Git 커밋이나 운영 배포가 아니다.
- 두 쓰기 API는 기존 로컬 요청 토큰을 요구한다. 초안 버전과 객체·관계·인터페이스 전체 원본 해시를 검사한다. 반영 중 실패하면 파일을 원복하고 초안을 보존한다.
- 원본 변경 시 자동 병합하지 않는다. 저장된 초안과 라이브러리 원본을 JSON으로 비교·내보낼 수 있다. 저장 중에는 편집 입력을 잠가 응답이 사용자 편집을 덮어쓰지 않게 한다.

객체 로더는 라이브러리에 반영된 계약만 구현 정보에 포함한다. 미반영 SQLite 초안은 관리 화면에서만 확인한다. 인터페이스 추가는 SQL 뷰의 행 단위·ID·컬럼 매핑 변경이 아니므로 기존 뷰 설계 해시는 객체·링크 정의를 대상으로 유지한다.

## 검증

`tests/test_interfaces.py`는 계약 검증과 임시 저장소를 사용한 저장·반영·경합·실패 롤백을 검사한다. `tests/interfaces-smoke.cjs`는 임시 라이브러리와 임시 SQLite에서 새 인터페이스·속성·관계·구현 매핑을 화면으로 작성하고, 재조회·반영·잘못된 PK 거부·원본 변경 시 초안 보존·요청 토큰·모바일 폭을 검증한다. 이 테스트는 사용자 라이브러리와 초안을 수정하지 않는다.

인터페이스 이름으로 실제 객체 데이터를 검색하거나 그래프를 탐색하는 실행 API는 이 관리 기능과 별개다. 이번 반영 범위는 계약·정적 검증·라이브러리 및 대시보드 관리 체계다.
