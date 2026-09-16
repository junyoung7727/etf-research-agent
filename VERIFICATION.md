# EDGE 검증 기록 · 2026-09-16

판정: **키 없는 공개 체험 앱·API 연결 코드·Android/iOS 빌드와 기동 완료. 실제 금융·LLM 인증과 스토어 출시는 미검증.** 원본 HTML·CSS·모션을 재사용했다. 로그인·알림은 제외하고 커뮤니티 목 자료·글·댓글·좋아요·의견 리포스트·투표·삭제·프로필 저장을 구현했다. 작성 내용은 기기별로 격리된다.

공개 주소: [EDGE 국내 ETF 데모](https://edge-etf-demo.asm-alphaeveryday.chatgpt.site). Sites 공개 버전 2에서 HTTPS·CSP·기기 저장과 아래 동선을 확인했다. 금융 서버는 이 주소의 Worker와 별도로 실행한다. 코드·키 입력 순서·페이지 모델은 [LAUNCH.md](LAUNCH.md)를 따른다.

## 실제 실행 증거

| 검사 | 결과 | 범위와 한계 |
|---|---|---|
| `npm test` | 11/11 PASS, skipped 0 | 금융 결측·0값·종목 계약·완료 봉 MA·비중 보존·CSP nonce |
| `npm run build` / `build:mobile` / `build:site` | PASS | TypeScript·프로덕션 번들. 500KB 청크 경고 있음 |
| Python 계약·프로토콜 검사 | 18/18 PASS | Windows와 최종 Python 3.13 Docker에서 실행. 실제 MCP 세션 + 모의 도구/DeepSeek 응답, 비공개 대화·예산·출처·키 미입력 검사 |
| 로컬 브라우저 검사 | 원본 6 + 커뮤니티 4 + 연결 4 PASS | 새 화면 14개 통과. 최초 전체 실행의 기존 UI 2개 실패는 `/legacy` 온보딩 조건 수정 후 기존 UI 5개 모두 재실행하여 PASS. 총 19개 범위, 단일 전체 재실행으로 보고하지 않음 |
| 공개 Chromium / WebKit 동선 | 두 브라우저 PASS | 온보딩 모션→ETF 선택→검색·시세→분석·출처→예시 대화→투표·글쓰기·재접속 저장·다른 방문자 격리. JS 예외 0, 외부 출처 요청 0, 금융 API POST 0 |
| 공개 HTTP | PASS | HTTPS 200, 명시적 DEMO 상태, 응답별 CSP nonce. 원본 비교 쿼리로 예시 표시 우회 불가 |
| Android | PASS | Java 21·SDK 36, Debug APK 빌드. API 36 에뮬레이터 설치·프로세스·캡처 직접 확인 |
| iOS | PASS | macOS·Xcode 26.6에서 시뮬레이터 앱 빌드·기동·캡처 확인. iPhone용 Release 앱도 서명 없이 컴파일 |
| Docker | PASS | 이미지 빌드, 비root 사용자, 영구 볼륨, 상태 검사. 공식 Kiwoom MCP 초기화·도구 목록 조회 성공, 키·시장 호출 없음 |
| 설정 점검 | PASS | 기본 `demoReady=true`, `liveConfigurationReady=false`. 누락된 변수 이름만 출력하고 외부 인증하지 않음 |
| `npm audit` | 취약점 보고 0 | 최종 의존성 설치 기준. 전체 보안 평가라는 뜻은 아님 |

네이티브 빌드: [GitHub Actions 35082890643](https://github.com/junyoung7727/etf-research-agent/actions/runs/35082890643), 소스 `e05099b2edd7d4378ce711525f871699ad7baa01`. 첫 iOS 실행 캡처가 빈 화면이어서 성공 판정을 철회하고, 대기·콘솔·실제 화면 렌더링 검사를 보강했다. 두 번째 실행에서 화면을 확인했다. 첫 빈 화면의 원인을 확정했다는 뜻은 아니다.

설치·검수 파일:

- [Android Debug APK](artifacts/releases/EDGE-demo-android.apk), 23,715,728 bytes. 개발 서명이며 Play Store 출시본이 아니다.
- [iOS 시뮬레이터 앱](artifacts/releases/EDGE-demo-ios-simulator.app.tar.gz), 20,984,875 bytes. macOS Simulator에서 설치한다.
- [iPhone용 서명 전 앱](artifacts/releases/EDGE-demo-ios-unsigned.app.tar.gz), 19,979,987 bytes. Apple 서명·프로비저닝 전에는 실제 iPhone에 배포할 수 없다.
- [빌드·파일 해시](artifacts/releases/manifest.json), [공개 브라우저 결과](artifacts/public-demo/results.json). GitHub Actions 임시 산출물은 14일 보관이며 로컬 사본을 별도로 남겼다.

## 디자인·모션 판정

원본 비교 모드에서 25개 상태의 텍스트와 모션 설정이 일치했다. 44개 프레임 중 43개는 픽셀 단위로 일치했다. `themes-1000.png` 사진 영역은 16,494픽셀이 다르고, 채널 차이 20/255를 넘는 픽셀은 137개다. **완전한 픽셀 동일성 검사는 실패 상태를 유지한다.** 비교 도구도 종료 코드 1을 반환한다. 자세한 조건은 [원본 재현 기록](ORIGINAL_REPRODUCTION.md)에 있다.

이는 원본 비교 모드의 수치다. 새 API 시트·체험 표시·복원된 커뮤니티까지 같은 픽셀이라고 주장하지 않는다. 실제 휴대폰 터치, 모든 화면의 Android/iOS 픽셀 비교는 실행하지 않았다.

## 키 입력 후와 별도로 남는 조건

| 항목 | 상태 |
|---|---|
| Kiwoom 실제 인증·허용 IP·장중 시세·만료·재구독 | NOT_RUN — 앱 자격증명 미입력 |
| DeepSeek 실제 모델·TinyFish HTTP 인증·Kiwoom MCP 실제 조회 | NOT_RUN — 모의 통합 검사와 구분 |
| 네이티브 HTTP의 실제 서버 쿠키·세션·실시간 연결 | NOT_RUN — 기본 앱은 오프라인 번들. 서버 주소를 넣은 재빌드 후 확인 |
| 외부 금융 서버 운영 배포 | 계정 연결 전 — Docker·Render 설정 준비, 로컬 컨테이너 확인. Sites에서 Python·stdio MCP는 실행하지 않음 |
| iOS 서명·스토어 등록 | Apple 계정·서명 전. Android도 스토어용 출시 서명 별도 |
| 운용사 실제 구성·보수·분배금 수집 | 미구현 — REAL은 자료 없음, DEMO는 명시된 자료 |
| 원본 뉴스·전망·테마·스토리 | 체험용 편집 자료. 자동 뉴스 수집·실제 투자 전망 엔진 아님 |
| LLM 주장과 원문 의미 일치·공격 문서 통합 평가 | NOT_RUN — 출처/인용 존재 검사만으로 사실성을 증명하지 않음 |
| 실부하·지연 p95·장중 복구·배포 환경 백업 복원 | NOT_RUN — 로컬 계약 검사를 성능/운영 검증으로 대체하지 않음 |
| 디스콰이엇 게시 | 공개 URL·공유 이미지 준비. 계정 게시 작업 미실행 |

Sites 첫 버전에서는 정적 HTML이 Worker를 우회해 보안 헤더가 없었다. 두 번째 버전은 HTML을 Worker 처리 경로로 보내 CSP·nonce·no-store를 실제 HTTP에서 확인했다. 공개 버전은 API 키를 포함하거나 실제 공급자를 호출하지 않는다. 기존 36개 검증 ID 전체를 PASS로 바꾸지 않는다.
