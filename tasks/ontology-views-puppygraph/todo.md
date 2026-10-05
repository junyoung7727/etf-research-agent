# 객체 뷰 → PuppyGraph 작업 체크리스트

계획: [plan.md](plan.md). 2026-10-05 사용자 승인 후 실행. 증거는 `output/ontology-views-puppygraph-20261005/`에 있다. 체크는 명시한 검증 범위의 완료이며 전체 CQ나 운영 전환 완료를 뜻하지 않는다.

- [x] 01 현재 정의와 실행 환경 고정
- [x] 02 모든 링크의 물리 매핑 분류
- [x] 03 대표 사례와 비교 데이터 고정
- [x] 04 뷰와 링크 매핑을 분리한 카탈로그 구현
- [x] 05 대시보드 상세와 ERD 수정
- [x] 06 설계 회귀 검증
- [x] 07 Company·Equity SQL 뷰 구현
- [x] 08 단순 FK의 PuppyGraph 매핑 구현
- [x] 09 단순 관계 양방향 대조
- [x] 10 SourceEvent·Organization 및 참여 원본 준비
- [x] 11 참여 엣지 매핑 구현
- [x] 12 Actor 인터페이스 조회 검증
- [x] 13 ETF·ETFHolding SQL 구현
- [x] 14 보유 관계와 Security 매핑 구현
- [x] 15 특정 ETF 전체 구성종목 조회 검증
- [x] 16 공시·뉴스 및 SourceDocument 경로 구현
- [x] 17 나머지 관계의 구현 순서 확정 및 작은 단위로 추가 분해
- [x] 18 나머지 객체와 링크 순차 구현 — 17에서 만든 각 단위별 통과 기록 필요
- [x] 19 전체 정합성 검증
- [x] 20 클라우드 재현 및 배포 검증
- [x] 21 대표 탐색의 성능 측정
- [x] 22 기본 CQ를 그래프에서 검증
- [x] 23 목적에 맞는 데이터 사용 평가
- [x] 24 완료·보류 최종 보고 — [report.md](report.md)

## 실행 증거

- 01–03: definition-inventory, live-db-audit, cloud-inventory. 객체 23개·링크 37개, 실제 복수 역할·NULL·없는 대상 사례 확보.
- 04–06: 물리 원본 27개와 논리 링크 분리. view-design 12개 및 브라우저 2종 통과. 전체 Python 78개 통과 뒤 NULL 엣지 회귀 추가, mapper 5개 통과.
- 07–09: core-deployment, core-graph-verification. 회사·주식 2,766개씩, 발행 관계 양방향 2,766쌍 일치.
- 10–12: participation-deployment, actor-graph-verification. 참여 ID·역할 보존, 선택 대상의 15,609개 참여 기록 및 역할 필터 일치.
- 13–15: 보유 기록 48,243개 보존. 방산 ETF 구성종목 10개를 한 질의로 대조. Security 타입 오연결 수정.
- 16: documents-graph-verification. 문서 31개·근거 141개 ID/신뢰도 일치.
- 17–18: [remaining-units.md](remaining-units.md). 객체별 15단위, 23개 객체 뷰·3개 준비 뷰 적용. 모든 속성 표본·정역방향 링크 대조. 빈 데이터와 CalculatedFrom 보류 별도 기록.
- 19: integrity, graph-edge-counts. SQL 고아 0건. 일봉 8,710,783건은 원본 PK·2,691개 증권 분할 및 그래프 표본 검사. 나머지 객체 ID 유일성, 일봉 외 34개 전체 엣지 수 일치.
- 20: redeployment. 정확한 Decimal 전송, 원본 변경 즉시 반영, 전체 23개 모델 복원·시험 뷰 삭제.
- 21–22: basic-cq. 단일·3종목·ETF 전체의 동일 가격 결과와 요청당 질의 1회 확인. 구성·공급자 역할·뉴스 근거·F01 자료 가용성 검증. 전체 CQ/LLM 자율 탐색은 미검증.
- 23: [coverage.md](coverage.md). 목적에 기여한 8개 객체·7개 링크를 기록하며 80% 달성을 주장하지 않음.
- 24: 최종 보고와 옵시디언 실행 기록 작성. 독립 PR 체크아웃의 79개 검사 중 최초 스냅샷 누락 15건, 추가 기준 JSON 누락 1건을 준비 조건으로 해소했다. 78개는 전체 실행에서, 나머지 1개는 기준 JSON 준비 후 집중 재실행에서 통과했다. 건너뛴 테스트는 없다. 두 브라우저 검사도 통과했다.

## 발견·수정한 문제

타입 라벨만 지정하면 없는 타입의 연결이 반환되어 실제 프로필로 해소했다. NULL 부모도 관계 수에 포함되어 모든 엣지 원본에 양끝 IS NOT NULL을 넣었다. Bolt Decimal의 float 손실은 SQL numeric을 유지하고 decimal_text 전송으로 해결했다. 30초를 넘긴 일봉 전체 ID 문자열 정렬과 자기 조인은 증권·날짜 조건 및 원본 PK·분할 집계로 나눴다.

## PR과 남은 경계

SQL은 PR #4–9, 대시보드·매핑·통합 시험은 [PR #10](https://github.com/junyoung7727/etf-research-agent/pull/10)에 있다. 순서대로 쌓은 draft이며 병합하지 않았다. GitHub 자동 검사는 설정돼 있지 않다.

기존 workbench가 Git 미추적 상태여서 #10의 첫 커밋에 기존 기준선을 보존하고 두 번째 커밋에 이번 변경을 분리했다. 로컬 library.json과 다른 사용자 변경은 제외했다. 기존 ELK·entities/app.js의 공백 경고는 원본 보존을 위해 유지했으며 이번 변경 diff의 공백 검사는 통과했다.

재무 보고 문맥 2건, 대상 증권이 DB에 없는 거래소 분류 1,720건은 NULL이다. 원가 구조 자료·사건 금액 특징 검색·현재 사건 상태 산출·계산 입력 연결은 해결되지 않았다. 클라우드는 private Fargate 시험 환경이며 운영 서비스 전환은 아니다.
