"""Initialize the installed Kiwoom MCP and inspect its tools without a market call."""
import asyncio
import json
import os
from contextlib import ExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def verify():
    env={k:os.environ[k] for k in ('PATH','SYSTEMROOT','WINDIR','HOME','USERPROFILE','TEMP','TMP') if k in os.environ}
    env.update({'APP_KEY':'','APP_SECRET':'','KIWOOM_PROFILE':'','KIWOOM_MODE':'real','KIWOOM_MCP_TRANSPORT':'stdio','KIWOOM_MCP_ALLOW_ORDERS':'0','KIWOOM_MCP_DEBUG_HEADERS':'0'})
    with ExitStack() as stack:
        log=stack.enter_context(open(os.devnull,'w'))
        async with asyncio.timeout(30),stdio_client(StdioServerParameters(command=os.getenv('KIWOOM_MCP_COMMAND','kiwoom-exec-mcp'),args=json.loads(os.getenv('KIWOOM_MCP_ARGS','[]')),env=env),errlog=log) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                names=[tool.name for tool in (await session.list_tools()).tools]
                if 'kiwoom_query' not in names or any('order' in name or 'debug' in name for name in names):raise RuntimeError('Unexpected MCP tool surface')
                print(json.dumps({'initialized':True,'tools':names,'marketCallsMade':False,'credentialsSupplied':False}))

if __name__=='__main__':asyncio.run(verify())
