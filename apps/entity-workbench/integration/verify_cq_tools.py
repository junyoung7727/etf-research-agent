"""Live graph tool verification; this is an integration check, not an LLM CQ run."""
import json
import sys
from datetime import datetime,timezone
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from backend.cq_tools import CQTools
from backend.puppygraph_viewer import reader
from backend.view_design import read_catalog


def verify():
    destination=APP.parents[1]/'output/cq-tools-benchmark-20261005/tool-integration'
    cutoff='2026-10-05T14:59:59+00:00'
    with reader() as run:
        provider=CQTools(run,read_catalog(),destination,cutoff)
        found=provider.call('search_objects',{'object_type':'ETF','filters':{'ticker':'449450'}})
        fund=found['result']['items'][0]
        ref={k:fund[k] for k in ('object_type','object_id')}
        holdings=provider.call('get_etf_holdings',{'etf_ref':ref,'holdings_date':'2026-10-05','date_policy':'latest_on_or_before','limit':2})
        assert holdings['result']['items']
        selected=holdings['result']['selection']
        dataset=provider.store.reference(holdings['result']['dataset_ref'],'dataset')
        assert len(dataset['items'])==len(selected['items'])>2
        assert not holdings['result']['page']['complete']
        actors,mapping=provider.actors(selected)
        assert actors and mapping
        report={'passed':True,'kind':'deterministic_graph_integration','agent_cq_test':False,
            'etf':fund['title'],'selection':selected,'full_dataset_rows':len(dataset['items']),
            'actor_count':len(actors),'queries':len(provider.graph.queries),
            'checked_at':datetime.now(timezone.utc).isoformat()}
        (destination/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k!='selection'},ensure_ascii=False))


if __name__=='__main__':verify()
