"""Verify all requested securities reached calculation, then compare actual agent calls."""
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_cq_agent import model_call_count

ROOT=Path(__file__).resolve().parents[3]/'output/cq-tools-benchmark-20261005'


def inspect(path,size):
    run=json.loads(path.read_text(encoding='utf8'))
    if run['status']!='answered':raise ValueError('Incomplete efficiency execution')
    source=next(json.loads(p.read_text(encoding='utf8')) for p in (ROOT/'efficiency'/(str(size)+'-0')).glob('cq_*.json')
                if json.loads(p.read_text(encoding='utf8'))['tool']=='get_price_observations')
    expected={r['object_id'] for r in source['response']['result']['selection']['items']}
    records=[json.loads(p.read_text(encoding='utf8')) for p in (path.parent/'tools').glob('cq_*.json')]
    calculations=[r for r in records if r['tool']=='calculate_returns' and not r['error'] and
                  r['dataset']['scope'].get('basis_policy')=='observed_close_only']
    reached={r['object_id'] for c in calculations for r in c['dataset']['items']}
    verified=reached==expected
    if not verified:raise ValueError('Complete requested set did not reach calculation')
    requested=model_call_count(path.parent)
    return {'run_id':path.parent.name,'tool_calls':requested,'persisted_tool_calls':run['tool_calls'],
        'schema_rejected_before_callback':requested-run['tool_calls'],'graph_queries':run['graph_queries'],
        'elapsed_ms':run['elapsed_ms'],'actual_targets':len(expected),'complete_set_verified':True,
        'calculation_batches':len(calculations),'largest_calculation_batch':max(len(c['dataset']['items']) for c in calculations),
        'public_response_bytes':sum(len(json.dumps(r['response'],ensure_ascii=False).encode()) for r in records),
        'basis_wording':'Review separately; unknown adjustment does not certify unadjusted prices.'}


if __name__=='__main__':
    comparison=[]
    for size in (1,5,30):
        paths=sorted((ROOT/'agent-runs').glob('EFF'+str(size).zfill(2)+'*/benchmark.json'))
        if len(paths)<2:raise ValueError('Before and after actual executions required')
        comparison.append({'scope':size,'before':inspect(paths[0],size),'after':inspect(paths[-1],size)})
    path=ROOT/'efficiency/report.json';report=json.loads(path.read_text(encoding='utf8'))
    report['agent_comparison']=comparison
    report['agent_measurement_limits']='One real model execution per scope and version; latency is not a stable percentile. Scope preservation is verified independently of answer semantics.'
    path.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(comparison))
