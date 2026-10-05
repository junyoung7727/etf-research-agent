"""Run independent real model CQ cases; each owns its graph connection and audit directory."""
import argparse
import asyncio
import json
from types import SimpleNamespace
from pathlib import Path
from run_cq_agent import execute,APP


async def main(args):
    contract=json.loads((APP/'data/cq-cases.json').read_text(encoding='utf8'))
    selected=[c for c in contract['cases'] if not args.cases or c['id'] in args.cases]
    if not selected:raise ValueError('No selected CQ cases')
    gate=asyncio.Semaphore(2)
    async def one(case):
        async with gate:
            try:
                await execute(SimpleNamespace(case=case['id']+'-suite',question=case['question'],
                    cutoff=contract['cutoff'],v2_source=args.v2_source))
            except Exception as exc:
                # Setup failure is visible and does not silently remove this CQ from the denominator.
                print(json.dumps({'case':case['id'],'setup_error':type(exc).__name__},ensure_ascii=False),flush=True)
    await asyncio.gather(*(one(c) for c in selected))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cases',nargs='*')
    parser.add_argument('--v2-source',default='D:/Github/edge/src/apps/cloud/analysis-engine-v2/src')
    asyncio.run(main(parser.parse_args()))
