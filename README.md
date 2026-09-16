# EDGE 웹 데모

국내 상장 ETF를 브라우저에서 살펴보는 독립 앱. React/TypeScript·JavaScript 화면과 FastAPI 서버를 같은 출처로 제공한다. 로그인·알림·커뮤니티는 제외했다.

**최신 디자인 검수본: <http://127.0.0.1:8018/original>.** 사용자가 제공한 MarketBrew HTML·CSS·JavaScript 원본과 모션을 패키지에 반영했다. 웹 코드를 재사용하는 경로이며 Flutter/Dart 재작성본이 아니다. [원본 재현·데이터 모델·검증 기록](ORIGINAL_REPRODUCTION.md)을 먼저 확인한다. 새 화면은 원본 예시 데이터를 사용하며 기존 서버 API 매핑은 아직 남아 있다.

**현재 상태: 로컬에서 동작하는 데모와 외부 연결 코드. 공개 출시 완료가 아니다.** 기본값은 명시된 예시 데이터다. 실제 Kiwoom·DeepSeek·MCP 인증, 장중 수신, 운용사 구성 자료 연결, 공개 서버 배포는 아직 검증하지 않았다. API 키가 없어도 데모를 실행할 수 있다.

## Windows에서 실행

Node 22.18 이상과 Python 3.12 이상을 권장한다. 개발 환경 검증은 Node 25.5 / Python 3.14 / Windows에서 수행했다.

```powershell
cd D:\Github\etf-research-agent\apps\edge
npm ci
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock.txt
npm run build
.venv/Scripts/python -m uvicorn server.app:app --host 127.0.0.1 --port 8018
```

원본 디자인 검수는 <http://127.0.0.1:8018/original>을 연다. <http://127.0.0.1:8018>에는 기존 API 연결 화면이 남아 있다. 이 기존 화면의 개발 중에는 서버와 별도로 `npm run dev`를 실행하고 <http://127.0.0.1:5178>을 사용한다. 루트 연구 도구의 `.env`는 자동으로 읽지 않는다.

## 현재 제공하는 동작

아래 기능·실연결 설명은 `/`의 기존 API 연결 화면에 해당한다. 원본 재현 화면의 적용 범위와 제외 동작은 [별도 기록](ORIGINAL_REPRODUCTION.md)에 있다.

- 온보딩, 테마 선택, 이름/코드/테마 검색, 최근 검색.
- 홈 브리핑, 관심 그룹 생성·종목 추가·여러 그룹 담기·드래그/버튼 재정렬·삭제·되돌리기. 그룹당 100개, 최대 20개 그룹.
- ETF 분석 날짜 전환·요인 설명·지표·출처, 일봉 차트·기간·이동평균·키보드 탐색·수치 표.
- 구성 히트맵의 종목/테마·일간/20일 전환, 비중/이름 정렬, 전체 구성과 미확인 잔여 비중.
- 테마와 이슈 상세, 개인 이름 변경, 온보딩 재진입, 개인 설정 초기화.

개인 설정은 이 브라우저에 저장된다. 기기 간 동기화는 없으며 여러 탭에서는 마지막 저장이 반영된다. 전망 점수와 테마 임계값은 정책 확정 전까지 판단 보류다. 베타 스토리는 포함 여부 확인 전까지 구현하지 않았다.

데모의 대상은 Figma에서 관찰한 ETF 6종이다. 시장 데이터가 실제로 연결되면 `EDGE_SYMBOLS`의 종목들이 Kiwoom ETF 목록에 있는지 검증한 후 제공한다. 국내 상장 ETF가 해외 자산을 편입할 수 있다. 별도 미국 주식 API는 연결하지 않는다.

## 실제 데이터로 전환

1. `.env.example`을 이 디렉터리의 `.env`로 복사한다. 값은 서버에서만 설정하고 채팅이나 프런트엔드 변수에 넣지 않는다.
2. `KIWOOM_APP_KEY`, `KIWOOM_APP_SECRET`, `EDGE_MODE=live`를 설정한다. 개발자센터에 서버의 송신 IP를 등록한다. REST 키는 이 앱에서 실전 조회용이며 모의투자 키와 섞지 않는다.
3. 서버를 한 프로세스로 실행한다. ETF 목록 조회 `ka40004`, 수정 일봉 `ka10081`, 체결 WebSocket `0B`를 사용한다. 주문·계좌 API는 제공하지 않는다.
4. 초기 목록을 조회한 뒤 서버 하나가 WS를 유지한다. 브라우저는 SSE로 공유 캐시를 받는다. 실패하면 마지막 값·시각·연결 이상을 표시하며 DEMO로 자동 전환하지 않는다.

첫 실연결에서 실제 응답 스키마·토큰 만료·등록 종목·휴장/무체결·재연결·지연을 확인해야 한다. 일봉은 안전하게 오늘 이전 날짜만 완료 봉으로 취급한다. 여러 서버 프로세스로 늘리기 전에 수집기·유량 제한을 분리해야 한다. 현재는 단일 프로세스용이다.

실제 편입 구성·보수·분배율·테마 핵심 지표·뉴스 데이터 수집은 미완료다. live 모드에서는 자료 없음으로 표시한다. 화면용 예시 비중을 실제 값으로 제공하지 않는다.

## DeepSeek + MCP

`server/analysis.py`가 DeepSeek의 도구 호출 제안을 검사한 후 실행한다. 공개 방문자는 도구 이름·프로필·모드·명령 경로를 지정할 수 없다.

- DeepSeek: 서버 전용 키와 현재 사용 가능한 모델 ID를 명시한다. 최대 3회 호출, 회당 출력 2,048토큰·입력 JSON 20KB.
- Kiwoom: 공식 Exec MCP의 stdio 명령을 `KIWOOM_MCP_COMMAND`와 JSON 배열 `KIWOOM_MCP_ARGS`로 지정한다. 예: 명령 `uv`, 인자 `["run","--frozen","--directory","D:/tools/Kiwoom-REST-API/mcp_exec","kiwoom-exec-mcp"]`. 서버 코드가 `ALLOW_ORDERS=0`, 진단 off, real 모드와 키를 명시적으로 전달한다. LLM에는 `domestic stocks info --code <현재 대상 ETF>`의 허용 필드만 반환한다.
- TinyFish: `https://agent.tinyfish.ai/mcp`에 서버용 Bearer 인증을 사용한다. 검색과 본문 추출만 허용한다. 검색에서 발견한 공식 도메인만 본문 조회 대상으로 삼으며 내부 주소·허용되지 않은 리다이렉트를 거부한다.
- 작업당 도구 6회, 총 60초, 동시 분석 2개. 종목/한국 시간 달력 날짜/정책별 중복 생성을 막는다. 동일 날짜의 성공한 결과는 불변 스냅샷으로 보존한다. 거래소 휴장일 달력은 아직 적용하지 않았다.
- `EDGE_DAILY_TOKEN_BUDGET` 기본값 0. 활성화하려면 작업당 보수적 예약량 80,000토큰 이상이어야 한다. 실패해도 예약량을 반환하지 않으며 SQLite에 기록하므로 재시작으로 예산이 초기화되지 않는다. 금액 상한은 선택한 모델 요금과 운영 예산 확인 후 별도로 확정해야 한다.

MCP의 실제 응답 형태와 무인 재시작 인증은 통합 검증 대상이다. 현재 연결된 Codex 도구의 인증이 이 앱으로 이전되는 것은 아니다. Kiwoom REST 수집기와 공식 MCP의 토큰 발급이 함께 동작하는지도 실제 계정에서 확인해야 한다. TinyFish 운용사 페이지 추출의 별도 확인은 시간 초과였다.

생성 문구의 숫자와 존재하지 않는 출처·원문 인용은 거부한다. 출처가 존재하고 인용이 일치해도 주장이 그 근거에서 논리적으로 따라오는지까지 자동 입증하는 것은 아니다. LLM 사실성 평가와 프롬프트 공격 통합 시험은 아직 남아 있다.

## 검증

```powershell
npm test
.venv/Scripts/python -m unittest server.test_contracts -v
npm run build
npx playwright install chromium
npm run test:e2e
```

브라우저 시험은 **빌드한 결과**를 검사하므로 화면 변경 후 build를 먼저 실행한다. [구조·페이지 모델·직접 검수 방법](ARCHITECTURE.md)과 [검증 기록](VERIFICATION.md)에 현재 구현과 남은 조건을 구분했다. [구현 계획](tasks/plan.md), [남은 작업](tasks/todo.md)을 함께 본다.

## 공개 배포 전

고정 송신 IP가 있는 Linux 서버에서 앱을 단일 프로세스로 실행하고, TLS 역방향 프록시 뒤에 둔다. 잠금 파일의 Windows 전용 의존성에는 플랫폼 마커가 있다. Linux 배포는 아직 실행 검증하지 않았다. `.venv/bin/python`으로 실행한다. `EDGE_PUBLIC_ORIGIN`을 실제 HTTPS 주소로 설정한다. API/정적 화면은 같은 출처로 제공하고 SSE 버퍼링을 끈다.

`data/`는 영구 볼륨으로 보존하고 외부에서 접근할 수 없게 한다. 이 디렉터리에는 분석 이력·일간 예산·익명 세션 서명 키가 있다. 앱과 데이터 백업·복원을 검증한다. 프록시가 전달한 실제 IP는 신뢰하는 프록시에서만 받도록 설정한다. 현재 서버는 `127.0.0.1:8018`에만 바인드한다.

공개 live 시세는 적용되는 재제공 권한을 확인한 후 `EDGE_MARKET_DATA_PUBLIC_USE_CONFIRMED=1`로 전환한다. 이 값은 권한을 부여하는 기능이 아니라 확인한 결정을 기록하는 설정이다. 외부 URL 검증과 디스콰이엇 실제 등록은 아직 하지 않았다.

## 디자인·외부 문서

아래는 첫 구현의 Figma 자산 기록이다. 최신 원본 HTML의 파일 해시·사진·글꼴·모션 기록은 [원본 재현 문서](ORIGINAL_REPRODUCTION.md)에 있다.

Figma의 Pretendard·색상·아이콘·테마 이미지를 사용했다. 아이콘과 이미지는 `public/figma/`에 원본 바이트로 저장했으며 런타임은 만료되는 Figma URL에 의존하지 않는다. `figma-assets.json`, `theme-assets.json`은 출처 기록이다. 원본 온보딩의 미구현 수집량·모델명 약속은 현재 기능에 맞게 고쳤다.

- [Figma 원본](https://www.figma.com/design/WzNipPm0ISeMQvVK5nmR1e)
- [Kiwoom 공식 Exec MCP](https://github.com/Kiwoom-Securities/Kiwoom-REST-API/tree/main/mcp_exec)
- [DeepSeek 도구 호출](https://api-docs.deepseek.com/guides/tool_calls/)
- [TinyFish MCP](https://docs.tinyfish.ai/mcp-integration)
