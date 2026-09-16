import asyncio
import hashlib
from contextlib import asynccontextmanager
import json
from pathlib import Path
import os
import re
import secrets
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .analysis import AnalysisRunner
from .data import AS_OF, demo_detail, demo_instruments
from .market import Market, now
from .security import Gate

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env', override=False)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instrumentId: str = Field(pattern=r'^[0-9A-Z]{6}$')


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: str = Field(pattern=r'^(user|assistant)$')
    text: str = Field(min_length=1, max_length=600)


class ChatRequest(AnalysisRequest):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=4)


def create_app(mode=None, data_dir=None):
    mode = mode or os.getenv('EDGE_MODE', 'demo')
    if mode not in ('demo', 'live'): raise ValueError('EDGE_MODE must be demo or live')
    origin = (os.getenv('EDGE_PUBLIC_ORIGIN') or os.getenv('RENDER_EXTERNAL_URL') or 'http://127.0.0.1:8018').rstrip('/')
    host = urlsplit(origin).hostname
    secure = origin.startswith('https://')
    if host not in ('localhost', '127.0.0.1') and not secure: raise ValueError('Public origin requires HTTPS')
    if mode == 'live' and host not in ('localhost', '127.0.0.1') and os.getenv('EDGE_MARKET_DATA_PUBLIC_USE_CONFIRMED') != '1':
        raise ValueError('Confirm applicable public market-data rights before publishing live data')
    allowed_origins = {origin}
    if not secure: allowed_origins.add('http://127.0.0.1:5178')
    storage = Path(data_dir) if data_dir else ROOT / 'data'
    storage.mkdir(parents=True, exist_ok=True)
    secret_path = storage / 'session-key'
    if not secret_path.exists(): secret_path.write_text(secrets.token_hex(32), encoding='utf-8')
    gate = Gate(secret_path.read_text(encoding='utf-8'))

    @asynccontextmanager
    async def lifespan(app):
        market = Market() if mode == 'live' else None
        app.state.market = market
        app.state.analysis = AnalysisRunner(market, storage / 'edge.sqlite')
        app.state.streams = 0
        task = asyncio.create_task(market.run()) if market else None
        try: yield
        finally:
            await app.state.analysis.close()
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if market: await market.close()

    app = FastAPI(title='EDGE ETF API', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list({host, 'localhost', '127.0.0.1', 'testserver'}))

    @app.middleware('http')
    async def security(request: Request, call_next):
        request_id = secrets.token_hex(8)
        session, new = gate.session(request.cookies.get('edge_session'))
        request.state.session = session
        ip = request.client.host if request.client else 'unknown'
        def reject(status, code, message):
            return JSONResponse({'error': {'code': code, 'message': message, 'requestId': request_id}}, status_code=status)
        if request.url.path.startswith('/api/'):
            if request.method not in ('GET', 'HEAD'):
                if request.headers.get('origin') not in allowed_origins:
                    return reject(403, 'ORIGIN_DENIED', '허용되지 않은 요청 출처입니다.')
                if request.headers.get('content-type', '').split(';')[0] != 'application/json':
                    return reject(415, 'JSON_REQUIRED', 'JSON 요청만 허용합니다.')
                size, chunks = 0, []
                async for chunk in request.stream():
                    size += len(chunk)
                    limit = 16_384 if request.url.path == '/api/chat-jobs' else 2048
                    if size > limit: return reject(413, 'BODY_TOO_LARGE', '요청이 너무 큽니다.')
                    chunks.append(chunk)
                request._body = b''.join(chunks)
            if not gate.allow('read:' + session, 30, 60) or not gate.allow('ip:' + ip, 180, 60):
                return reject(429, 'RATE_LIMITED', '요청이 많아요. 잠시 후 다시 시도해 주세요.')
        try: response = await call_next(request)
        except Exception:
            response = reject(503, 'SERVICE_UNAVAILABLE', '요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Request-ID'] = request_id
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"
        if request.url.path.startswith('/flutter/'):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
        if getattr(request.state, 'style_nonce', None):
            response.headers['Content-Security-Policy'] = response.headers['Content-Security-Policy'].replace("style-src 'self';", f"style-src 'self' 'nonce-{request.state.style_nonce}';")
        if secure: response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if request.url.path.startswith('/api/'): response.headers['Cache-Control'] = 'no-store'
        if new: response.set_cookie('edge_session', session, httponly=True, secure=secure, samesite='strict', max_age=86400)
        return response

    @app.get('/api/health')
    async def health():
        return {'status': 'ok', 'mode': mode.upper(), 'version': '0.1.0'}

    @app.get('/api/catalog')
    async def catalog():
        if mode == 'demo':
            return {'instruments': demo_instruments(), 'dataMode': 'DEMO', 'asOf': AS_OF, 'feedState': 'DEMO', 'analysisEnabled': False}
        market = app.state.market
        if not market.items: raise HTTPException(503, '실데이터 연결이 준비되지 않았어요. 서버 API 설정을 확인해 주세요.')
        return {'instruments': list(market.items.values()), 'dataMode': 'REAL', 'asOf': now().isoformat(),
                'feedState': market.state, 'analysisEnabled': app.state.analysis.enabled}

    @app.get('/api/etfs/{symbol}')
    async def detail(symbol: str):
        if mode == 'demo':
            instrument = next((i for i in demo_instruments() if i['id'] == symbol), None)
            if not instrument: raise HTTPException(404, '이번 데모의 국내 ETF 목록에 없는 종목입니다.')
            return demo_detail(instrument)
        market = app.state.market
        if symbol not in market.items: raise HTTPException(404, '등록된 국내 ETF가 아닙니다.')
        candles = await market.candles(symbol)
        return {'instrument': market.items[symbol], 'candles': candles, 'holdings': [], 'holdingsAsOf': None,
                'holdingsStatus': 'MISSING', 'residualWeight': 1,
                'fundamentals': [{'label': label, 'value': None} for label in ('총보수 (연)', '분배율 (연)', '순자산', '추적오차')],
                'analyses': app.state.analysis.snapshots(symbol), 'dataMode': 'REAL'}

    @app.get('/api/quotes/stream')
    async def quotes(request: Request):
        if app.state.streams >= 40: raise HTTPException(429, '현재 실시간 접속이 많아요.')
        app.state.streams += 1
        async def events():
            try:
                for _ in range(1800):
                    if await request.is_disconnected(): break
                    yield 'data: ' + json.dumps(await catalog(), ensure_ascii=False) + '\n\n'
                    await asyncio.sleep(2)
            finally: app.state.streams -= 1
        return StreamingResponse(events(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})

    @app.post('/api/analysis-jobs')
    async def create_job(body: AnalysisRequest, request: Request):
        cookie = request.state.session
        ip = request.client.host if request.client else 'unknown'
        if not gate.allow('job:' + cookie, 2, 600) or not gate.allow('job-ip:' + ip, 6, 600):
            raise HTTPException(429, '새 분석 요청 한도에 도달했어요.')
        try: return app.state.analysis.submit(body.instrumentId)
        except ValueError as error:
            message = '분석 제공자 설정과 예산을 확인해 주세요.' if str(error) == 'ANALYSIS_NOT_CONFIGURED' else '분석 대상·동시 실행 수·일간 예산을 확인해 주세요.'
            raise HTTPException(503, message) from None

    @app.get('/api/analysis-jobs/{job_id}')
    async def job(job_id: str, request: Request):
        if len(job_id) > 100: raise HTTPException(404, '작업을 찾을 수 없어요.')
        owner = hashlib.sha256(request.state.session.encode()).hexdigest()
        result = app.state.analysis.job(job_id, owner)
        if not result: raise HTTPException(404, '작업을 찾을 수 없어요.')
        return result

    @app.post('/api/chat-jobs')
    async def chat(body: ChatRequest, request: Request):
        cookie = request.state.session
        ip = request.client.host if request.client else 'unknown'
        if not body.message.strip(): raise HTTPException(422, '질문을 입력해 주세요.')
        if not gate.allow('chat:' + cookie, 6, 600) or not gate.allow('chat-ip:' + ip, 12, 600):
            raise HTTPException(429, '질문 요청 한도에 도달했어요. 잠시 후 다시 시도해 주세요.')
        if mode == 'demo':
            instrument = next((i for i in demo_instruments() if i['id'] == body.instrumentId), None)
            if instrument is None: raise HTTPException(404, '등록된 국내 ETF가 아닙니다.')
            report = demo_detail(instrument)['analyses'][0]
            return {'id':'demo-chat', 'instrumentId':body.instrumentId, 'state':'SUCCEEDED', 'failureCode':None,
                    'response':{'text':'예시 답변입니다. ' + report['headline'] + '\n\n' + report['summary'],
                                'sources':report['sources'], 'asOf':report['asOf'], 'modelId':'demo-fixture-v1', 'dataMode':'DEMO'}}
        try:
            return app.state.analysis.submit(body.instrumentId, question=body.message.strip(),
                history=[message.model_dump() for message in body.history], owner=hashlib.sha256(cookie.encode()).hexdigest())
        except ValueError:
            raise HTTPException(503, '분석 제공자 설정과 예산 또는 동시 실행 한도를 확인해 주세요.') from None

    flutter_web = ROOT.parent / 'edge_flutter/build/web'
    if flutter_web.exists():
        app.mount('/flutter', StaticFiles(directory=flutter_web, html=True), name='flutter-design-review')
    if (ROOT / 'dist/assets').exists():
        app.mount('/assets', StaticFiles(directory=ROOT / 'dist/assets'), name='assets')
    app.mount('/figma', StaticFiles(directory=ROOT / 'public/figma'), name='figma')
    app.mount('/original-assets', StaticFiles(directory=ROOT / 'public/original-assets'), name='original-assets')

    @app.api_route('/og.png', methods=['GET', 'HEAD'])
    async def social_preview():
        return FileResponse(ROOT / 'public/og.png', media_type='image/png')

    @app.get('/')
    @app.get('/original')
    async def original_review(request: Request):
        request.state.style_nonce = secrets.token_urlsafe(24)
        html = (ROOT / 'dist/original.html').read_text(encoding='utf-8')
        html = html.replace('<head>', f'<head><meta name="style-nonce" content="{request.state.style_nonce}">', 1)
        return HTMLResponse(html, headers={'Cache-Control': 'no-store'})

    @app.get('/{path:path}')
    async def frontend(path: str):
        known = path in ('legacy', 'watch', 'search', 'explore') or re.fullmatch(r'(etf|issue)/[0-9A-Z]{6}', path) or (path.startswith('theme/') and len(path) < 100)
        if not known or not (ROOT / 'dist/index.html').exists():
            raise HTTPException(404, '찾을 수 없는 페이지입니다.')
        return FileResponse(ROOT / 'dist/index.html')

    return app


app = create_app()
