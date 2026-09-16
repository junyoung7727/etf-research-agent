# EDGE · 국내 ETF 데모

MarketBrew 원본 HTML·CSS·모션을 React/JavaScript·TypeScript로 재사용하고, 같은 화면을 Capacitor Android·iOS 앱으로 묶는다. 로그인·알림은 제외했다. 커뮤니티의 글·댓글·좋아요·의견 리포스트·투표·프로필은 **기기별 체험 데이터**이며 다른 방문자에게 게시되지 않는다.

공개 데모: https://edge-etf-demo.asm-alphaeveryday.chatgpt.site

현재 배포와 모바일 실행의 실제 판정은 [검증 기록](VERIFICATION.md)에 있다. 공개 웹과 기본 모바일 패키지는 명시된 예시 자료를 사용한다. 금융·AI 서버는 별도 FastAPI/Docker 프로그램이다. 공개 데모의 배포 성공이 Kiwoom 인증 성공을 뜻하지 않는다.

## 로컬 실행

작업 디렉터리는 `apps/edge`. Node 22 이상, Python 3.13 이상을 사용한다. 루트 연구 프로젝트의 환경 파일은 읽지 않는다.

```powershell
npm ci
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock.txt
npm run build
.venv/Scripts/python -m uvicorn server.app:app --host 127.0.0.1 --port 8018
```

`http://127.0.0.1:8018/`와 `/original`은 원본 기반 화면이다. 이전 API 검수 화면은 `/legacy`에 보존했다. Docker는 `docker compose up --build -d`로 실행하고 `http://127.0.0.1:8025/`에서 확인한다.

## 구현 범위

온보딩·관심 ETF/테마·그룹·검색·탐색·이슈·스토리·상세와 모션, 커뮤니티·기기 저장을 제공한다. 가격·등락·일봉·MA5/20·구성·기본 정보·날짜별 분석·지표·출처·AI 대화는 서버 모델과 연결했다. 대기·실패·자료 없음·재시도를 표시한다.

기본 실시간 연결 대상은 6종이며 `src/original/market-view.ts`의 `SYMBOLS`가 내부 키를 종목코드에 대응한다. REAL 모드에서 Kiwoom ETF 목록으로 국내 상장 여부를 검증한다. 해외 자산을 편입한 국내 상장 ETF도 포함한다.

실제 구성·보수·분배율 원자료가 없으면 `MISSING`이다. 원본 탐색 순위·뉴스·스토리·전망은 예시라고 표시한다. 실제 생성 결과는 **연결된 분석·출처**에서 확인한다. 자동 뉴스 대량 수집·예약 분석·매매는 제공하지 않는다.

## API와 모바일

[LAUNCH.md](LAUNCH.md)에 페이지 모델, 수학적 검수 조건, 보안 경계, 키 입력 순서를 정리했다. 키는 서버 `.env` 또는 호스팅의 비밀 환경 변수에만 입력한다. 프런트엔드·APK·iOS 앱·채팅에는 넣지 않는다.

```powershell
.venv/Scripts/python -m server.preflight
npm run mobile:sync
npx cap open android
# macOS에서: npx cap open ios
```

기본 모바일 앱은 오프라인 데모다. 실제 연결 빌드는 `EDGE_API_ORIGIN=https://서버주소`만 설정하고 `npm run mobile:sync`를 다시 실행한다. 서버 API 키를 빌드에 포함하지 않는다. Android는 Java 21·SDK 36, iOS는 macOS·Xcode 26 이상을 사용한다. 앱 스토어 서명·등록은 별도 계정이 필요하다.

`.github/workflows/mobile.yml`이 독립 `edge-mobile-demo` 브랜치에서 APK·iOS 앱을 빌드·기동한다. 루트 연구 코드는 이 브랜치에 포함하지 않는다. `tools/stage-release.py`는 Git에서 제외하지 않은 앱 파일만 별도 배포 디렉터리로 복사한다.

## 검증과 배포

```powershell
npm test
.venv/Scripts/python -m unittest server.test_contracts server.test_provider_protocol -v
npm run build
npx playwright install chromium
npm run test:e2e
```

원본 비교용 `?fixture=original`은 로컬 개발 빌드에만 남긴다. Docker·모바일·공개 웹에서는 비활성화한다. 원본과 자산 해시는 보존했다. [재현 기록](ORIGINAL_REPRODUCTION.md)에 비교 조건과 남은 차이가 있다.

Sites에는 키 없는 공개 데모를 배포한다. 별도 소스 저장소 `private/edge-publish`의 `.openai/hosting.json` 프로젝트를 재사용한다. `npm run build:site`는 `dist/client`와 Worker를 만든다. 실제 금융 서버는 `Dockerfile`·`compose.yaml`·`render.yaml`을 사용한다. Render 설정은 과금 가능한 starter 서비스이며 계정 연결 없이 자동 구매하지 않는다. 서버는 단일 프로세스와 영구 `data/` 볼륨을 사용한다.

실제 Kiwoom 서버의 송신 IP를 등록해야 한다. Render 공유 대역을 하나의 고정 IP로 간주하면 안 된다. [Render 송신 IP](https://render.com/docs/outbound-ip-addresses), [Capacitor 환경](https://capacitorjs.com/docs/getting-started/environment-setup), [공식 Kiwoom MCP](https://github.com/Kiwoom-Securities/Kiwoom-REST-API/tree/main/mcp_exec), [DeepSeek 도구 호출](https://api-docs.deepseek.com/guides/tool_calls/), [TinyFish MCP](https://docs.tinyfish.ai/mcp-integration).
