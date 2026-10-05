"""Same analytical request for 1/5/30 actual securities; the model chooses its own calls."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from run_cq_agent import execute,APP


async def main():
    root=APP.parents[1]/'output/cq-tools-benchmark-20261005/efficiency'
    gate=asyncio.Semaphore(2)
    async def one(size):
        records=[json.loads(p.read_text(encoding='utf8')) for p in (root/(str(size)+'-0')).glob('cq_*.json')]
        prices=next(r for r in records if r['tool']=='get_price_observations')
        members=prices['response']['result']['selection']['items']
        labels=[m['object']['title']+' ('+m['object']['properties']['ticker']+')' for m in members]
        question=('다음 한국 주식 전체를 대상으로 2026-10-01에서 2026-10-02까지 관측 종가 변화와 '
            '상승·하락·보합·미확인 분포를 확인해 주세요. 명시한 모든 종목을 포함하고, '
            '자료가 없는 종목은 제외하지 말고 구분해 주세요. 종가 변화와 조정 수익률을 구분하세요. '
            '결론은 간단히 요약하고 대표 움직임은 최대 세 종목만 제시하세요.\n대상: '+', '.join(labels))
        async with gate:
            await execute(SimpleNamespace(case='EFF'+str(size).zfill(2),question=question,
                cutoff='2026-10-05T14:59:59+00:00',v2_source='D:/Github/edge/src/apps/cloud/analysis-engine-v2/src'))
    await asyncio.gather(*(one(n) for n in (1,5,30)))


if __name__=='__main__':asyncio.run(main())
