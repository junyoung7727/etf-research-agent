import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import httpx
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from .analysis import AnalysisRunner, RESERVATION
from .data import demo_detail, demo_instruments
from .preflight import inspect


class FakeMarket:
    appkey='test-kiwoom-key';secret='test-kiwoom-secret'
    items={i['id']:i for i in demo_instruments()}
    async def candles(self,symbol):return demo_detail(self.items[symbol])['candles']
    async def pace(self):pass


class ProviderProtocol(unittest.IsolatedAsyncioTestCase):
    async def test_llm_http_tool_rounds_use_real_mcp_wire_and_only_the_selected_etf(self):
        calls=[];source='https://www.tigeretf.com/test-evidence'
        text='투자 대상과 자료의 기준일을 공식 문서에서 확인해야 합니다.'
        def tool(name,args):return {'id':name,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}
        async def transport(request):
            self.assertEqual(str(request.url),'https://api.deepseek.com/chat/completions')
            self.assertEqual(request.headers['authorization'],'Bearer test-deepseek-key')
            body=json.loads(request.content);calls.append(body)
            self.assertNotIn('test-kiwoom',request.content.decode())
            self.assertEqual(body['model'],'test-model')
            if len(calls)==1:message={'role':'assistant','content':None,'tool_calls':[tool('get_quote',{}),tool('search_sources',{'query':'공식 문서'})]}
            elif len(calls)==2:message={'role':'assistant','content':None,'tool_calls':[tool('fetch_source',{'url':source})]}
            else:message={'role':'assistant','content':json.dumps({'headline':'투자 대상을 확인해요','claims':[{'text':'공식 문서의 기준일을 확인해요.','sourceId':'source-1','quote':text}]})}
            return httpx.Response(200,json={'choices':[{'message':message}]})
        original_http=httpx.AsyncClient
        @asynccontextmanager
        async def kiwoom(params,**kwargs):
            self.assertEqual(params.env['KIWOOM_MCP_ALLOW_ORDERS'],'0')
            self.assertEqual(params.env['KIWOOM_MODE'],'real')
            self.assertNotIn('DEEPSEEK_API_KEY',params.env)
            async with stdio_client(StdioServerParameters(command=sys.executable,args=['-m','server.fixture_mcp','kiwoom'])) as streams:yield streams
        @asynccontextmanager
        async def tiny(url,**kwargs):
            self.assertEqual(url,'https://agent.tinyfish.ai/mcp')
            self.assertEqual(kwargs['headers'],{'Authorization':'Bearer test-tinyfish-token'})
            async with stdio_client(StdioServerParameters(command=sys.executable,args=['-m','server.fixture_mcp','tiny'])) as streams:yield (*streams,None)
        async def destination(url,client):return url
        with tempfile.TemporaryDirectory() as folder:
            runner=AnalysisRunner(FakeMarket(),Path(folder)/'test.db')
            runner.api_key='test-deepseek-key';runner.model='test-model';runner.tiny_token='test-tinyfish-token';runner.kiwoom_command='fixture'
            try:
                with patch('server.analysis.stdio_client',kiwoom),patch('server.analysis.streamablehttp_client',tiny),patch('server.analysis.check_destination',destination),patch('server.analysis.httpx.AsyncClient',lambda **kw:original_http(transport=httpx.MockTransport(transport),**kw)):
                    report=await runner.generate('396500',question='어떤 근거를 확인하나요?',history=[])
                self.assertEqual(len(calls),3)
                self.assertEqual(report['sources'][0]['url'],source)
                self.assertEqual(report['summary'],'공식 문서의 기준일을 확인해요.')
                self.assertIsNone(report['outlook'])
                self.assertEqual(calls[-1]['tool_choice'],'none')
            finally:await runner.close()

    async def test_chat_results_belong_to_one_session_and_never_enter_public_etf_history(self):
        with tempfile.TemporaryDirectory() as folder:
            runner=AnalysisRunner(FakeMarket(),Path(folder)/'test.db')
            runner.enabled=True;runner.daily_budget=RESERVATION*4
            async def generate(symbol,**kwargs):return demo_detail(FakeMarket.items[symbol])['analyses'][0]
            runner.generate=generate
            try:
                a=runner.submit('396500',question='확인할 근거는?',owner='alice')
                self.assertEqual(runner.submit('396500',question='확인할 근거는?',owner='alice')['id'],a['id'])
                b=runner.submit('396500',question='확인할 근거는?',owner='bob')
                self.assertNotEqual(a['id'],b['id'])
                self.assertIsNone(runner.job(a['id'],'bob'));self.assertIsNone(runner.job(a['id']))
                await asyncio.gather(*runner.tasks)
                self.assertEqual(runner.job(a['id'],'alice')['state'],'SUCCEEDED')
                self.assertEqual(runner.snapshots('396500'),[])
                self.assertEqual(runner.db.execute('SELECT reserved FROM budget').fetchone()[0],RESERVATION*2)
            finally:await runner.close()


class PreflightContract(unittest.TestCase):
    def test_empty_configuration_is_usable_as_demo_and_never_claims_live_authentication(self):
        result=inspect({})
        self.assertTrue(result['demoReady']);self.assertFalse(result['liveConfigurationReady']);self.assertFalse(result['externalCallsMade'])
        self.assertIn('KIWOOM_APP_KEY',result['missing'])

    def test_preflight_never_prints_secret_values_or_accepts_invalid_budget_and_origin(self):
        result=inspect({'KIWOOM_APP_KEY':'canary-secret','EDGE_PUBLIC_ORIGIN':'http://public.example','EDGE_DAILY_TOKEN_BUDGET':'NaN'})
        self.assertNotIn('canary-secret',json.dumps(result))
        self.assertIn('INVALID_PUBLIC_ORIGIN',result['problems'])
        self.assertIn('TOKEN_BUDGET_NOT_INTEGER',result['problems'])
