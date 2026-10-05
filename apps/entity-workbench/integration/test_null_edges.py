import json
from pilot_graph import graph_session,read_catalog
from pilot_session import OUT
integrity=json.loads((OUT/'integrity.json').read_text(encoding='utf8'));catalog=read_catalog();report={}
with graph_session([o['id'] for o in catalog['objects']]) as (session,_):
    for r in catalog['relations']:
        n=r['id'];m=r['physicalMapping']
        if m['kind']=='blocked' or m.get('source')=='DailyBar':continue
        count=session.run('MATCH (a:'+r['source']+')-[r:'+n+']->(b:'+r['target']+') RETURN count(r) AS n').single()['n']
        expected=integrity['links'][n]['linkedRows'];assert count==expected,(n,count,expected)
        report[n]={'graphEdges':count,'sqlEdges':expected,'exact':True};print(n,count,flush=True)
        (OUT/'graph-edge-counts.json').write_text(json.dumps(report,indent=2),encoding='utf8')
