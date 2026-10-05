"""Deploy reviewed attributes, then compare the new names in SQL and PuppyGraph."""
import json,sys
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from pilot_graph import graph_session
from pilot_session import database
from backend.view_design import read_catalog
from backend.graph_queries import name,interface_traversal
from backend.interface_types import source_catalog

OUT=APP.parents[1]/'output/ontology-readable-views-20261005'

catalog=read_catalog();objects={o['id']:o for o in catalog['objects']}
contract=json.loads((APP/'data/view-display-contracts.json').read_text(encoding='utf-8'))['objects']
report={'objects':{},'deployedObjectCount':len(objects)}
with database() as db,db.cursor() as c:
    c.execute('SELECT count(*) FROM public.price_daily');base_count=c.fetchone()[0]
    c.execute('SELECT count(*),count(security_name),count(security_ticker) FROM ontology_view.daily_bar')
    row=c.fetchone();assert row[0]==base_count
    report['dailyBarFullCount']={'base':base_count,'view':row[0],'named':row[1],'ticker':row[2],
                                'identityMethod':'source primary key, unchanged JSON-array encoding, and joins to unique instrument/entity IDs'}
    samples={}
    for kind,spec in contract.items():
        obj=objects[kind];view=obj['viewName'];props=list(spec['mappings'])
        cols=[spec['mappings'][p]['column'] for p in props]
        c.execute('SELECT id,'+','.join(cols)+' FROM '+view+' LIMIT 3')
        samples[kind]={r[0]:dict(zip(props,r[1:])) for r in c.fetchall()}
        nulls=[]
        if kind!='DailyBar':
            c.execute('SELECT '+','.join('count(*) FILTER (WHERE '+col+' IS NULL)' for col in cols)+' FROM '+view)
            nulls=dict(zip(props,c.fetchone()))
        report['objects'][kind]={'nullableDisplayFields':nulls,'sampleSize':len(samples[kind])}
    c.execute("SELECT etf_name,security_name,security_ticker,trade_date,weight_ratio,display_title FROM ontology_view.etf_holding WHERE etf_ticker='449450' AND trade_date=(SELECT max(trade_date) FROM ontology_view.etf_holding WHERE etf_ticker='449450') ORDER BY security_ticker")
    report['defenseEtfExample']=c.fetchall()

with graph_session(list(objects)) as (session,_):
    for kind,expected in samples.items():
        if not expected:
            report['objects'][kind]['graph']='no source rows'
            continue
        props=list(contract[kind]['mappings']);conditions=['n.id IN $ids'];params={'ids':list(expected)}
        if kind=='DailyBar':
            # Explicit partition predicate keeps composite graph-ID lookup bounded.
            params['instruments']=list({json.loads(i)[0] for i in expected})
            conditions.append('n.instrumentId IN $instruments')
        q='MATCH (n:'+name(kind)+') WHERE '+' AND '.join(conditions)+' RETURN n.id AS id,'+','.join('n.'+name(p)+' AS '+name(p) for p in props)
        actual={r['id']:{p:r[p] for p in props} for r in session.run(q,params)}
        assert actual==expected,(kind,actual,expected)
        report['objects'][kind]['graph']='exact match'
        print(kind,'SQL/graph display properties match',flush=True)
    interfaces={i['name']:i for i in source_catalog()['catalog']['interfaces']}
    r=session.run("MATCH (s:Equity) WHERE s.ticker='012450' RETURN s.id AS id LIMIT 1").single()
    q,params=interface_traversal(interfaces['Security'],'heldIn',[{'type':'Equity','id':r['id']}],catalog)
    result=[r.data() for r in session.run(q,params)]
    assert result and all(r['targetTitle'] and r['targetId'] for r in result)
    report['agentTraversal']={'rows':len(result),'titleAndIdTogether':True,'examples':result[:2]}
report['passed']=True
(OUT/'graph-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
print('Display graph verification passed')
