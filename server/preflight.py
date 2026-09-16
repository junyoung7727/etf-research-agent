"""Local configuration inspection. Never displays keys or calls providers."""
import argparse
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit
from dotenv import load_dotenv


def inspect(env):
    required=('KIWOOM_APP_KEY','KIWOOM_APP_SECRET','DEEPSEEK_API_KEY','DEEPSEEK_MODEL','TINYFISH_MCP_TOKEN','KIWOOM_MCP_COMMAND')
    missing=[name for name in required if not env.get(name,'').strip()]
    problems=[]
    command=env.get('KIWOOM_MCP_COMMAND','')
    if command and not (shutil.which(command) or Path(command).is_file()): problems.append('KIWOOM_MCP_COMMAND_NOT_FOUND')
    try:
        args=json.loads(env.get('KIWOOM_MCP_ARGS','[]'))
        if not isinstance(args,list) or any(not isinstance(v,str) for v in args): raise ValueError()
    except (ValueError,TypeError): problems.append('KIWOOM_MCP_ARGS_NOT_STRING_ARRAY')
    try: budget=int(env.get('EDGE_DAILY_TOKEN_BUDGET','0'))
    except ValueError: budget=0;problems.append('TOKEN_BUDGET_NOT_INTEGER')
    if budget<80000: missing.append('EDGE_DAILY_TOKEN_BUDGET (minimum 80000)')
    origin=env.get('EDGE_PUBLIC_ORIGIN') or env.get('RENDER_EXTERNAL_URL') or 'http://127.0.0.1:8018'
    parsed=urlsplit(origin)
    local=parsed.hostname in ('localhost','127.0.0.1')
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username or (not local and parsed.scheme!='https'):
        problems.append('INVALID_PUBLIC_ORIGIN')
    if not local and env.get('EDGE_MARKET_DATA_PUBLIC_USE_CONFIRMED')!='1': missing.append('EDGE_MARKET_DATA_PUBLIC_USE_CONFIRMED')
    mode=env.get('EDGE_MODE','demo')
    if mode not in ('demo','live'):problems.append('INVALID_MODE')
    return {'mode':mode,'demoReady':mode=='demo' and not problems,'liveConfigurationReady':not missing and not problems,
            'missing':missing,'problems':problems,'externalCallsMade':False,
            'nextVerification':['Register server egress IP with Kiwoom','Verify real token, ETF catalogue and market-hours feed','Verify DeepSeek model and both MCP tools with bounded budget'],
            'scope':'Configuration only; provider authentication and market-data rights are not verified by this command.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-live',action='store_true')
    args=parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent.parent/'.env',override=False)
    report=inspect(os.environ)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if (report['liveConfigurationReady'] if args.require_live else report['demoReady'] or report['liveConfigurationReady']) else 2)
