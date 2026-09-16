import asyncio
from datetime import timedelta
from decimal import Decimal
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx

from .analysis import AnalysisRunner, RESERVATION, allowed_url, validate_report, validate_tool_call, mcp_payload, source_from_fetch
from mcp.types import CallToolResult, TextContent
from .app import create_app
from .data import demo_detail, demo_instruments, factors, number, ratio
from .market import Market, now, quote_from_row
from .security import Gate


class DataContract(unittest.TestCase):
    def test_signed_price_and_difference_keep_decline_negative(self):
        quote = quote_from_row({'stk_cd': '396500', 'close_pric': '-9700', 'pred_pre': '300', 'pre_sig': '5'}, 'now')
        self.assertEqual(quote['price'], '9700')
        self.assertEqual(quote['previousClose'], '10000')
        self.assertEqual(Decimal(quote['changeRatio']), Decimal('-.03'))
        self.assertIsNone(number('')); self.assertIsNone(number('NaN')); self.assertIsNone(ratio(Decimal(100), Decimal(0)))

    def test_demo_snapshots_reconcile_without_fabricating_missing_facts(self):
        for instrument in demo_instruments():
            detail = demo_detail(instrument)
            self.assertEqual(detail['dataMode'], 'DEMO')
            self.assertEqual(detail['candles'][-1]['close'], instrument['quote']['price'])
            self.assertAlmostEqual(sum(h['weight'] for h in detail['holdings']) + detail['residualWeight'], 1)
            self.assertTrue(all(f['value'] is None for f in detail['fundamentals']))
        self.assertEqual(demo_detail(demo_instruments()[0])['residualWeight'], .2701)

    def test_ma_needs_20_closes_but_return_needs_21(self):
        candles = [{'close': str(v), 'isComplete': True} for v in range(100, 120)]
        metrics = factors(candles)[1]['metrics']
        self.assertEqual(Decimal(metrics[0]['value']), Decimal('109.5'))
        self.assertIsNone(metrics[1]['value'])
        candles.append({'close': '120', 'isComplete': True})
        self.assertEqual(Decimal(factors(candles)[1]['metrics'][1]['value']), Decimal('20'))


class SecurityContract(unittest.TestCase):
    def test_tinyfish_text_and_final_url_are_checked_from_observed_contract(self):
        url = 'https://www.bok.or.kr/portal/main/main.do'
        raw = {'results': [{'url': url, 'final_url': url, 'title': '한국은행', 'text': '테스트용 문서입니다. 실제 금융 수치는 아닙니다.'}]}
        self.assertEqual(source_from_fetch(raw, url, 's1')['excerpt'], raw['results'][0]['text'])
        raw['results'][0]['final_url'] = 'https://127.0.0.1/private'
        with self.assertRaises(ValueError): source_from_fetch(raw, url, 's1')
        with self.assertRaises(ValueError): source_from_fetch({'results': [], 'errors': [{'error': 'timeout'}]}, url, 's1')

    def test_mcp_wrapped_and_plain_json_contracts(self):
        value = {'stk_cd': '396500', 'cur_prc': '103'}
        self.assertEqual(mcp_payload(CallToolResult(content=[], structuredContent={'result': value})), value)
        self.assertEqual(mcp_payload(CallToolResult(content=[TextContent(type='text', text=json.dumps(value))])), value)
        with self.assertRaises(ValueError): mcp_payload(CallToolResult(content=[], isError=True))

    def test_tool_calls_cannot_choose_accounts_commands_or_other_symbols(self):
        validate_tool_call('get_quote', {}, set())
        for name, arguments in [('kiwoom_query', {'command_path': 'domestic accounts balance'}), ('get_quote', {'code': '005930'}), ('get_quote', {'mode': 'real'}), ('search_sources', {'query': 'x', 'url': 'http://127.0.0.1'}), ('fetch_source', {'url': 'https://evil.example'})]:
            with self.subTest(name=name, arguments=arguments), self.assertRaises(ValueError): validate_tool_call(name, arguments, set())

    def test_sources_must_be_public_allowed_hosts_and_discovered_first(self):
        self.assertTrue(allowed_url('https://www.tigeretf.com/product'))
        for url in ['http://www.tigeretf.com', 'https://127.0.0.1', 'https://169.254.169.254', 'https://tigeretf.com.evil.test', 'https://user:pass@www.tigeretf.com', 'https://www.tigeretf.com:8443']:
            self.assertFalse(allowed_url(url), url)
        with self.assertRaises(ValueError): validate_tool_call('fetch_source', {'url': 'https://www.tigeretf.com/product'}, set())

    def test_quote_and_source_ids_are_checked_and_generated_numbers_rejected(self):
        source = {'id': 's1', 'excerpt': '공식 자료의 기준일과 투자 대상을 확인해야 합니다.'}
        raw = {'headline': '구성을 확인해요', 'claims': [{'text': '자료의 기준일을 확인해요.', 'sourceId': 's1', 'quote': source['excerpt']}]}
        validate_report(json.dumps(raw), [source])
        raw['claims'][0]['sourceId'] = 'made-up'
        with self.assertRaises(ValueError): validate_report(json.dumps(raw), [source])
        raw['claims'][0]['sourceId'] = 's1'; raw['claims'][0]['text'] = '수익률은 99%예요.'
        with self.assertRaises(ValueError): validate_report(json.dumps(raw), [source])

    def test_session_signature_and_rate_limit(self):
        gate = Gate('test-secret'); cookie, new = gate.session(None)
        self.assertTrue(new); self.assertEqual(gate.session(cookie), (cookie, False))
        self.assertTrue(gate.session(cookie + 'x')[1])
        self.assertTrue(gate.allow('visitor', 1, 60)); self.assertFalse(gate.allow('visitor', 1, 60))

    def test_http_rejects_cross_origin_extra_fields_oversize_and_no_provider(self):
        with tempfile.TemporaryDirectory() as folder, TestClient(create_app('demo', folder)) as client:
            response = client.get('/api/catalog')
            self.assertEqual(response.status_code, 200)
            self.assertIn('HttpOnly', response.headers['set-cookie'])
            self.assertIn("script-src 'self'", response.headers['content-security-policy'])
            self.assertEqual(client.get('/api/etfs/AAPL').status_code, 404)
            for route in ('posts', 'votes', 'orders', 'accounts', 'mcp'):
                self.assertEqual(client.get('/api/' + route).status_code, 404)
            self.assertEqual(client.post('/api/analysis-jobs', json={'instrumentId': '396500'}).status_code, 403)
            headers = {'origin': 'http://127.0.0.1:8018'}
            self.assertEqual(client.post('/api/analysis-jobs', json={'instrumentId': '396500', 'command_path': 'orders'}, headers=headers).status_code, 422)
            self.assertEqual(client.post('/api/analysis-jobs', json={'instrumentId': 'x' * 3000}, headers=headers).status_code, 413)
            self.assertEqual(client.post('/api/analysis-jobs', json={'instrumentId': '396500'}, headers=headers).status_code, 503)
            self.assertNotIn('secret', client.get('/api/health').text)

    def test_live_failure_never_returns_demo_prices(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'KIWOOM_APP_KEY': '', 'KIWOOM_APP_SECRET': ''}), TestClient(create_app('live', folder)) as client:
            response = client.get('/api/catalog')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('12806', response.text)


class AsyncContract(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_token_refresh_has_one_owner(self):
        calls = []
        async def transport(request):
            calls.append(request.url.path)
            return httpx.Response(200, json={'token': 'private-canary', 'expires_dt': (now() + timedelta(hours=1)).strftime('%Y%m%d%H%M%S'), 'return_code': 0})
        market = Market(httpx.AsyncClient(transport=httpx.MockTransport(transport)))
        market.appkey = 'test-key'; market.secret = 'test-secret'
        result = await asyncio.gather(*[market.access_token() for _ in range(10)])
        self.assertEqual(len(calls), 1); self.assertEqual(set(result), {'private-canary'})
        with self.assertRaises(ValueError): await market.request('kt10000', {})
        self.assertEqual(len(calls), 1)
        await market.close()

    async def test_disconnect_preserves_last_value_and_marks_it_stale(self):
        market = Market()
        market.items = {'396500': demo_instruments()[0]}
        prior = market.items['396500']['quote']['price']
        market.stale()
        self.assertEqual(market.items['396500']['quote']['price'], prior)
        self.assertEqual(market.items['396500']['quote']['status'], 'STALE')
        self.assertEqual(market.state, 'DISCONNECTED')
        await market.close()

    async def test_duplicate_jobs_share_one_run_and_budget_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            market = Market(); market.items = {'396500': demo_instruments()[0]}
            runner = AnalysisRunner(market, Path(folder) / 'db.sqlite'); runner.enabled = True; runner.daily_budget = RESERVATION
            started = asyncio.Event(); release = asyncio.Event(); calls = []
            async def generate(symbol):
                calls.append(symbol); started.set(); await release.wait()
                return {'id': '', 'asOf': now().isoformat(), 'headline': '검증용 결과'}
            runner.generate = generate
            first = runner.submit('396500'); second = runner.submit('396500')
            self.assertEqual(first['id'], second['id'])
            await started.wait(); release.set(); await asyncio.gather(*list(runner.tasks))
            self.assertEqual(calls, ['396500']); self.assertEqual(runner.job(first['id'])['state'], 'SUCCEEDED')
            await runner.close()
            restored = AnalysisRunner(market, Path(folder) / 'db.sqlite')
            self.assertEqual(len(restored.snapshots('396500')), 1)
            self.assertEqual(restored.db.execute('SELECT reserved FROM budget').fetchone()[0], RESERVATION)
            await restored.close(); await market.close()


if __name__ == '__main__': unittest.main()
