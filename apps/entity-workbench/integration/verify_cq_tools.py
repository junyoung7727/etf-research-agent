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
        events=provider.call('search_events',{'targets':{'kind':'selection_ref','ref':{
            'tool_run_id':holdings['tool_run_id'],'path':'/selection'}},'start_date':'2026-09-01',
            'end_date':'2026-10-05','time_field':'reported_event_date','event_types':['COMPANY.CONTRACT.SIGNING'],'limit':2})
        assert 'dataset_ref' in events['result'],events
        event_data=provider.store.reference(events['result']['dataset_ref'],'dataset')['items']
        assert event_data
        targets={'kind':'selection_ref','ref':{'tool_run_id':holdings['tool_run_id'],'path':'/selection'}}
        prices=provider.call('get_price_observations',{'targets':targets,'start_date':'2026-09-28','end_date':'2026-10-02','limit':2})
        assert 'dataset_ref' in prices['result'],prices
        financials=provider.call('get_financial_observations',{'targets':targets,'kind':'actual','fiscal_years':[2026],'limit':2})
        assert 'dataset_ref' in financials['result'],financials
        documents=provider.call('search_documents',{'targets':targets,'start_date':'2026-09-28','end_date':'2026-10-02','limit':2})
        assert 'dataset_ref' in documents['result'],documents
        previous=provider.call('get_previous_analyses',{'etf_ref':ref,'before':cutoff,'limit':2})
        assert 'dataset_ref' in previous['result'],previous
        factors=provider.call('get_security_classifications',{'targets':targets,'factors':['industry'],'limit':2})
        assert 'dataset_ref' in factors['result'],factors
        report={'passed':True,'kind':'deterministic_graph_integration','agent_cq_test':False,
            'etf':fund['title'],'selection':selected,'full_dataset_rows':len(dataset['items']),
            'actor_count':len(actors),'queries':len(provider.graph.queries),
            'events_returned':len(event_data),'event_features_present':any(e['features'] for e in event_data),
            'price_rows':prices['result']['total_rows'],'financial_rows':financials['result']['total_rows'],
            'document_rows':documents['result']['total_rows'],'previous_reports':previous['result']['total_rows'],
            'checked_at':datetime.now(timezone.utc).isoformat()}
        (destination/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k!='selection'},ensure_ascii=False))


if __name__=='__main__':verify()
