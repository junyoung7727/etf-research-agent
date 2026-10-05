"""Measure actual graph batching separately from autonomous CQ quality; no fabricated p95."""
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

APP=Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from backend.cq_tools import CQTools
from backend.puppygraph_viewer import reader
from backend.view_design import read_catalog


def main():
    root=APP.parents[1]/'output/cq-tools-benchmark-20261005/efficiency'
    cutoff='2026-10-05T14:59:59+00:00';catalog=read_catalog();records=[]
    with reader() as run:
        discover=CQTools(run,catalog,root/'discovery',cutoff)
        refs=discover.graph.query('MATCH (n:Equity) WHERE n.marketCode=$market RETURN n.id AS id ORDER BY n.id LIMIT 30',{'market':'XKRX'},objects=['Equity'])
        refs=[{'object_type':'Equity','object_id':r['id']} for r in refs]
        fund=discover.graph.nodes('ETF',filters={'ticker':'449450'})[0]
        fund_ref={k:fund[k] for k in ('object_type','object_id')}
        if len(refs)!=30:raise ValueError('Thirty actual Korean securities are required')
        for size in (1,5,30,'ETF_all'):
            for repeat in range(3):
                provider=CQTools(run,catalog,root/(str(size)+'-'+str(repeat)),cutoff)
                target={'kind':'objects','object_refs':refs[:size]} if isinstance(size,int) else {
                    'kind':'etf_holdings','etf_ref':fund_ref,'holdings_date':'2026-10-02','date_policy':'exact'}
                started=perf_counter()
                prices=provider.call('get_price_observations',{'targets':target,'start_date':'2026-10-01','end_date':'2026-10-02','limit':2})
                returns=provider.call('calculate_returns',{'dataset_ref':prices['result']['dataset_ref'],
                    'start_date':'2026-10-01','end_date':'2026-10-02','price_field':'closePrice','basis_policy':'observed_close_only'})
                breadth=provider.call('summarize_price_breadth',{'dataset_ref':returns['result']['dataset_ref']})
                elapsed=round((perf_counter()-started)*1000,2)
                selection=prices['result']['selection'];full=provider.store.reference(returns['result']['dataset_ref'],'dataset')
                assert len(full['items'])==len(selection['items'])
                assert sum(r['count'] for r in breadth['result']['items'])==len(selection['items'])
                assert not any(c['error'] for c in provider.store.calls)
                records.append({'requested_scope':size,'repeat':repeat,'actual_targets':len(selection['items']),
                    'tool_calls':len(provider.store.calls),'graph_queries':len(provider.graph.queries),
                    'public_response_bytes':sum(len(json.dumps(c['response'],ensure_ascii=False).encode()) for c in provider.store.calls),
                    'elapsed_ms':elapsed,'graph_query_ms':sum(q['elapsed_ms'] for q in provider.graph.queries),
                    'page_limit':2,'all_targets_reached_calculation':True,'tool_errors':0})
    report={'kind':'deterministic_batch_performance','autonomous_agent_test':False,'source':'cloud PuppyGraph',
        'question':'Observed close changes and directional breadth for the complete requested securities',
        'records':records,'summary':[{ 'scope':size,'median_ms':statistics.median(r['elapsed_ms'] for r in records if r['requested_scope']==size),
            'graph_query_counts':sorted({r['graph_queries'] for r in records if r['requested_scope']==size})} for size in (1,5,30,'ETF_all')],
        'limits':['Three samples per scope, sequential shared connection; no p95 claim.',
            'Graph statements are measured, not the SQL statements PuppyGraph executes internally.',
            'Model-selected tool-call efficiency is measured separately in saved real CQ executions.']}
    (root/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report['summary']))


if __name__=='__main__':main()
