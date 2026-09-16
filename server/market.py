"""One account connection and shared quote cache; market-data methods only."""
import asyncio
import json
import os
import re
import time
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
import websockets

from .data import CATALOG, decimal_text, factors, number, ratio

KST = ZoneInfo('Asia/Seoul')
REST = 'https://api.kiwoom.com'
WS = 'wss://api.kiwoom.com:10000/api/dostk/websocket'
PATHS = {'ka40004': '/api/dostk/etf', 'ka10081': '/api/dostk/chart'}


def now():
    return datetime.now(KST)


def quote_from_row(row, fetched):
    price = number(row.get('close_pric'), absolute=True)
    change = number(row.get('pred_pre'))
    if change is not None:
        # Some responses encode direction separately from the absolute difference.
        sign = str(row.get('pre_sig', ''))
        if sign in ('4', '5'): change = -abs(change)
        elif sign in ('1', '2'): change = abs(change)
        elif sign == '3': change = Decimal(0)
    previous = price - change if price is not None and change is not None else None
    if price is not None and price <= 0: price = None
    return {'price': decimal_text(price), 'previousClose': decimal_text(previous),
            'changeRatio': decimal_text(ratio(price, previous)), 'asOf': fetched, 'receivedAt': fetched,
            'status': 'STALE' if price is not None else 'MISSING',
            'snapshotId': f'kiwoom:{row["stk_cd"]}:{fetched}', 'feedState': 'CONNECTING'}


class Market:
    def __init__(self, client=None):
        self.client = client or httpx.AsyncClient(timeout=12, follow_redirects=False)
        self.appkey = os.getenv('KIWOOM_APP_KEY', '')
        self.secret = os.getenv('KIWOOM_APP_SECRET', '')
        configured = os.getenv('EDGE_SYMBOLS', ','.join(row[0] for row in CATALOG))
        self.symbols = list(dict.fromkeys(configured.split(',')))
        if not self.symbols or len(self.symbols) > 200 or any(not re.fullmatch(r'[0-9A-Z]{6}', s) for s in self.symbols):
            raise ValueError('EDGE_SYMBOLS must contain 1–200 domestic ETF codes')
        self.token = ''; self.expires = 0; self.token_lock = asyncio.Lock()
        self.throttle = asyncio.Lock(); self.last_request = 0.
        self.items = {}; self.candle_cache = {}; self.candle_lock = asyncio.Lock()
        self.state = 'CONNECTING'; self.error = None; self.last_message = 0.

    async def pace(self):
        async with self.throttle:
            await asyncio.sleep(max(0, .26 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()

    async def access_token(self):
        async with self.token_lock:
            if self.token and time.time() < self.expires - 90: return self.token
            if not self.appkey or not self.secret: raise RuntimeError('KIWOOM_NOT_CONFIGURED')
            await self.pace()
            response = await self.client.post(REST + '/oauth2/token', json={
                'grant_type': 'client_credentials', 'appkey': self.appkey, 'secretkey': self.secret})
            response.raise_for_status(); body = response.json()
            if body.get('return_code', 0) != 0 or not body.get('token'): raise RuntimeError('KIWOOM_AUTH_FAILED')
            self.expires = datetime.strptime(body['expires_dt'], '%Y%m%d%H%M%S').replace(tzinfo=KST).timestamp()
            self.token = body['token']; return self.token

    async def request(self, api_id, payload, continuation=None):
        if api_id not in PATHS: raise ValueError('MARKET_METHOD_NOT_ALLOWED')
        token = await self.access_token(); await self.pace()
        headers = {'api-id': api_id, 'authorization': f'Bearer {token}', 'content-type': 'application/json;charset=UTF-8'}
        if continuation: headers.update({'cont-yn': 'Y', 'next-key': continuation})
        response = await self.client.post(REST + PATHS[api_id], json=payload, headers=headers)
        if response.status_code == 401: self.expires = 0
        response.raise_for_status(); body = response.json()
        if body.get('return_code', 0) != 0: raise RuntimeError('KIWOOM_QUERY_FAILED')
        return body, response.headers.get('next-key') if response.headers.get('cont-yn') == 'Y' else None

    async def bootstrap(self):
        found, continuation = {}, None
        meta = {r[0]: (index, r) for index, r in enumerate(CATALOG)}
        for _ in range(30):
            data, continuation = await self.request('ka40004', {'txon_type': '0', 'navpre': '0', 'mngmcomp': '0000', 'txon_yn': '0', 'trace_idex': '0', 'stex_tp': '1'}, continuation)
            fetched = now().isoformat()
            if not isinstance(data.get('etfall_mrpr'), list): raise RuntimeError('KIWOOM_SCHEMA_CHANGED')
            for row in data['etfall_mrpr']:
                symbol = row.get('stk_cd')
                if symbol not in self.symbols: continue
                index, seed = meta.get(symbol, (0, (symbol, '', '', '국내주식', '#4431e9')))
                found[symbol] = {'id': symbol, 'name': row['stk_nm'], 'shortName': row['stk_nm'],
                                 'theme': seed[3], 'color': seed[4], 'icon': index, 'currency': 'KRW',
                                 'quote': quote_from_row(row, fetched)}
            if set(found) == set(self.symbols) or not continuation: break
        if set(found) != set(self.symbols): raise RuntimeError('CONFIGURED_ETF_NOT_IN_PROVIDER_CATALOG')
        self.items = {s: found[s] for s in self.symbols}

    def update_trade(self, entry):
        symbol = entry.get('item'); values = entry.get('values', {})
        if entry.get('type') != '0B' or symbol not in self.items: return
        price = number(values.get('10'), absolute=True)
        change = number(values.get('11'))
        trade_clock = str(values.get('20', ''))
        if price is None or price <= 0 or change is None or len(trade_clock) != 6: return
        received = now(); trade = datetime.strptime(received.strftime('%Y%m%d') + trade_clock, '%Y%m%d%H%M%S').replace(tzinfo=KST)
        if trade > received + timedelta(seconds=5): return
        old = self.items[symbol]['quote']
        if old.get('tradeAt') and trade.isoformat() < old['tradeAt']: return
        previous = price - change
        self.items[symbol]['quote'] = {'price': decimal_text(price), 'previousClose': decimal_text(previous),
            'changeRatio': decimal_text(ratio(price, previous)), 'asOf': trade.isoformat(), 'tradeAt': trade.isoformat(),
            'receivedAt': received.isoformat(), 'status': 'READY', 'feedState': 'CONNECTED',
            'snapshotId': f'kiwoom:{symbol}:{received.isoformat()}'}

    def stale(self):
        self.state = 'DISCONNECTED'
        for item in self.items.values():
            item['quote']['feedState'] = self.state
            if item['quote']['price'] is not None: item['quote']['status'] = 'STALE'

    async def run(self):
        attempt = 0
        while True:
            try:
                await self.bootstrap()
                token = await self.access_token()
                async with websockets.connect(WS, max_size=2_000_000, open_timeout=12, close_timeout=3) as socket:
                    await socket.send(json.dumps({'trnm': 'LOGIN', 'token': token}))
                    logged_in = False
                    while True:
                        message = json.loads(await asyncio.wait_for(socket.recv(), timeout=25))
                        self.last_message = time.monotonic()
                        kind = message.get('trnm')
                        if kind == 'PING': await socket.send(json.dumps(message)); continue
                        if kind == 'LOGIN':
                            if str(message.get('return_code')) != '0': self.expires = 0; raise RuntimeError('WS_AUTH_FAILED')
                            logged_in = True
                            await socket.send(json.dumps({'trnm': 'REG', 'grp_no': '1', 'refresh': '1', 'data': [{'item': self.symbols, 'type': ['0B']}]}))
                        elif kind == 'REG':
                            if str(message.get('return_code', 0)) != '0': raise RuntimeError('WS_SUBSCRIPTION_FAILED')
                            self.state = 'CONNECTED'; self.error = None; attempt = 0
                            for item in self.items.values(): item['quote']['feedState'] = self.state
                        elif kind == 'REAL' and logged_in:
                            self.state = 'CONNECTED'; self.error = None; attempt = 0
                            for entry in message.get('data', []): self.update_trade(entry)
                        if time.time() >= self.expires - 90: break
            except asyncio.CancelledError: raise
            except Exception:
                self.error = '시장 데이터 연결을 확인하고 있어요.'
            self.stale(); attempt += 1
            await asyncio.sleep(min(60, 2 ** min(attempt, 6)))

    async def candles(self, symbol):
        if symbol not in self.items: raise ValueError('ETF_NOT_ALLOWED')
        async with self.candle_lock:
            cached = self.candle_cache.get(symbol)
            if cached and time.monotonic() - cached[0] < 300: return cached[1]
            data, _ = await self.request('ka10081', {'stk_cd': symbol, 'base_dt': now().strftime('%Y%m%d'), 'upd_stkpc_tp': '1'})
            rows = data.get('stk_dt_pole_chart_qry')
            if not isinstance(rows, list): raise RuntimeError('KIWOOM_CANDLE_SCHEMA_CHANGED')
            candles = {}
            for row in rows[:600]:
                day = datetime.strptime(row['dt'], '%Y%m%d').date()
                values = {out: number(row.get(raw), absolute=True) for out, raw in [('open', 'open_pric'), ('high', 'high_pric'), ('low', 'low_pric'), ('close', 'cur_prc')]}
                if any(v is None or v <= 0 for v in values.values()): continue
                if not values['low'] <= min(values['open'], values['close']) <= max(values['open'], values['close']) <= values['high']: raise RuntimeError('INVALID_CANDLE')
                candles[day.isoformat()] = {'date': day.isoformat(), **{k: decimal_text(v) for k, v in values.items()},
                    'volume': int(number(row.get('trde_qty')) or 0), 'isComplete': day < now().date()}
            result = [candles[k] for k in sorted(candles)][-250:]
            self.candle_cache[symbol] = (time.monotonic(), result); return result

    async def close(self): await self.client.aclose()
