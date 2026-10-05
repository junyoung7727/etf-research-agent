import json
import sys
from datetime import date,datetime,timezone
from decimal import Decimal
from pilot_graph import graph_session,read_catalog
from pilot_session import OUT,database

catalog=read_catalog();objects={o['id']:o for o in catalog['objects']};tables={t['id']:t for t in catalog['physicalTables']}
report={'nodes':{},'links':{},'blocked':[]}
if '--resume' in sys.argv:report=json.loads((OUT/'all-graph-verification.json').read_text(encoding='utf8'))
def save(): (OUT/'all-graph-verification.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf8')
def normalized(value):
    if hasattr(value,'to_native'):value=value.to_native()
    if isinstance(value,datetime):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value,list):return tuple(value)
    return value

with graph_session(list(objects)) as (session,meta),database() as conn,conn.cursor() as c:
    report['schema']=meta
    for n,o in objects.items():
        if n in report['nodes']:continue
        cols=[x for x in o['columns'] if x.get('property')]
        projection=','.join(x['column'] for x in cols)
        extra='';params={}
        if n=='DailyBar':
            c.execute('SELECT instrument_id FROM ontology_view.daily_bar LIMIT 1');inst=c.fetchone()[0]
            c.execute('SELECT '+projection+' FROM '+o['viewName']+' WHERE instrument_id=%s LIMIT 100',(inst,))
            extra=' AND n.instrumentId=$instrument';params['instrument']=inst
        else:c.execute('SELECT '+projection+' FROM '+o['viewName']+' LIMIT 100')
        rows=c.fetchall();ids=[row[0] for row in rows];params['ids']=ids
        expected={row[0]:tuple(normalized(v) for v in row) for row in rows}
        query='MATCH (n:'+n+') WHERE n.id IN $ids'+extra+' RETURN '+','.join('n.'+x['property']+' AS p'+str(i) for i,x in enumerate(cols))
        actual={}
        for row in session.run(query,params):
            values=[]
            for col,v in zip(cols,row.values()):
                if col['type']=='numeric' and v is not None:
                    assert isinstance(v,str),(n,col['property'],type(v).__name__)
                    v=Decimal(v)
                values.append(normalized(v))
            assert values[0] not in actual
            actual[values[0]]=tuple(values)
        assert actual==expected,(n,next(((k,expected.get(k),actual.get(k)) for k in expected.keys()|actual.keys() if expected.get(k)!=actual.get(k)),None))
        report['nodes'][n]={'passed':True,'exactAllPropertiesSamples':len(rows),'empty':not rows};save();print(n,len(rows),flush=True)
    for link in catalog['relations']:
        m=link['physicalMapping'];name=link['id']
        if name in report['links']:continue
        if m['kind']=='blocked':report['blocked'].append(name);continue
        t=tables[m['source']];conditions=['v.'+m['fromColumn']+' IS NOT NULL','v.'+m['toColumn']+' IS NOT NULL'];sqlparams=[]
        extra_graph='';graph_params={}
        if m['source']=='DailyBar':
            c.execute('SELECT instrument_id FROM '+t['viewName']+' WHERE security_type=%s LIMIT 1',(m['filters']['security_type'][0],))
            sample=c.fetchone()
            if sample:
                conditions.append('v.instrument_id=%s');sqlparams.append(sample[0])
                extra_graph=' AND s.instrumentId=$instrument';graph_params['instrument']=sample[0]
        for col,values in m['filters'].items():conditions.append('v.'+col+'=ANY(%s)');sqlparams.append(values)
        fields=[m['fromColumn'],m['toColumn'],*m['edgeIdColumns'],*m['properties'].values()]
        c.execute('SELECT '+','.join('v.'+x for x in fields)+' FROM '+t['viewName']+' v WHERE '+' AND '.join(conditions)+' LIMIT 100',sqlparams)
        rows=c.fetchall()
        # Compare every edge for the selected source IDs, including duplicate roles.
        source_ids=list({r[0] for r in rows});conditions.append('v.'+m['fromColumn']+'=ANY(%s)');sqlparams.append(source_ids)
        joins=''
        if not (m['source']==link['source'] and m['fromColumn']=='id'):joins+=' JOIN '+objects[link['source']]['viewName']+' s ON s.id=v.'+m['fromColumn']
        if not (m['source']==link['target'] and m['toColumn']=='id'):joins+=' JOIN '+objects[link['target']]['viewName']+' z ON z.id=v.'+m['toColumn']
        c.execute('SELECT '+','.join('v.'+x for x in fields)+' FROM '+t['viewName']+' v'+joins+' WHERE '+' AND '.join(conditions),sqlparams)
        expected=sorted((tuple(normalized(v) for v in r) for r in c.fetchall()),key=repr)
        result_fields=['s.id','z.id']+['r.key_'+str(i) for i in range(len(m['edgeIdColumns']))]+['r.'+p for p in m['properties']]
        pattern='(s:'+link['source']+')-[r:'+name+']->(z:'+link['target']+')'
        query='MATCH '+pattern+' WHERE s.id IN $ids'+extra_graph+' RETURN '+','.join(v+' AS p'+str(i) for i,v in enumerate(result_fields))
        graph_params['ids']=source_ids
        actual=sorted((tuple(normalized(v) for v in r.values()) for r in session.run(query,graph_params)),key=repr)
        assert actual==expected,(name,len(actual),len(expected),list(set(actual)-set(expected))[:2],list(set(expected)-set(actual))[:2])
        reverse=query.replace(pattern,'(z:'+link['target']+')<-[r:'+name+']-(s:'+link['source']+')')
        backward=sorted((tuple(normalized(v) for v in r.values()) for r in session.run(reverse,graph_params)),key=repr)
        assert backward==expected,name+' reverse'
        report['links'][name]={'passed':True,'rows':len(actual),'exactForwardReverse':True,'empty':not rows};save();print(name,len(actual),flush=True)
report['passed']=True;save()
