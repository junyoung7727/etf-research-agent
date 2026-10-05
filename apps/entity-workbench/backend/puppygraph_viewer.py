"""Bounded, read-only visualization of the deployed PuppyGraph; no schema writes."""
import json
from contextlib import contextmanager
from datetime import date, datetime, timezone
from backend.view_design import read_catalog
from backend.graph_queries import name

ROOT_TYPES = ('ETF', 'Company', 'Equity', 'Organization')


def catalog():
    current = read_catalog()
    return {'objects': [{'id':o['id'], 'description':o['description'],
                         'properties':[c for c in o['columns'] if c.get('property')],
                         'encodings':o.get('graphValueEncodings',{})} for o in current['objects']],
            'relations':[{'id':r['id'], 'source':r['source'], 'target':r['target'],
                          'inverse':r['inverse'], 'description':r['description'],
                          'blocked':r['physicalMapping']['kind']=='blocked'} for r in current['relations']],
            'rootTypes':ROOT_TYPES, 'modelChanged':current['modelChanged'],
            'scope':'현재 PuppyGraph 실데이터 · 조회마다 원본 확인 · 읽기 전용'}


@contextmanager
def reader():
    # Reuse the already verified private pilot connection. Credentials stay server-side.
    from integration.pilot_session import state, tunnel
    from neo4j import GraphDatabase, Query
    aws, runtime, credentials = state()
    try:
        with tunnel(aws, runtime['ip'], 7687) as port:
            with GraphDatabase.driver(f'bolt://127.0.0.1:{port}',
                    auth=(credentials['username'],credentials['password']),
                    connection_timeout=10, connection_acquisition_timeout=15) as driver:
                with driver.session(default_access_mode='READ') as session:
                    yield lambda query, parameters: [r.data() for r in session.run(Query(query, timeout=25),parameters)]
    finally:
        credentials.clear()


def execute(query, parameters):
    with reader() as run:
        return run(query, parameters)


def connections(kind='', identifier='', cursor='', run=None, design=None):
    """Page every deployed relation, preserving direction, roles and all dates."""
    design = design or read_catalog()
    if design['modelChanged']:
        raise ValueError('객체 모델 변경 후 그래프 매핑을 먼저 갱신하세요.')
    if bool(kind) != bool(identifier) or (kind and kind not in {o['id'] for o in design['objects']}):
        raise ValueError('유효한 객체 타입과 ID를 함께 지정하세요.')
    if len(identifier) > 2000:
        raise ValueError('객체 ID가 너무 깁니다.')
    links = [r for r in design['relations'] if r['physicalMapping']['kind'] != 'blocked'
             and (not kind or kind in (r['source'], r['target']))]
    offsets = {r['id']: {'offset':0,'partition':0} for r in links}
    if cursor:
        try:
            saved = json.loads(cursor)
            if saved['scope'] != [kind, identifier]: raise ValueError()
            offsets = saved['offsets']
            if not isinstance(offsets, dict) or set(offsets) != {r['id'] for r in links}: raise ValueError()
            if any(v is not None and (not isinstance(v,dict) or set(v)!={'offset','partition'} or
                   any(type(n) is not int or n<0 for n in v.values())) for v in offsets.values()): raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise ValueError('조회 범위에 맞지 않는 이어보기 정보입니다.') from None
    if run is None:
        with reader() as session_run:
            return connections(kind, identifier, cursor, session_run, design)
    nodes, edges = {}, []
    for link in links:
        relation = link['id']; position = offsets[relation]
        if position is None: continue
        offset = position['offset']; params = {'id':identifier} if kind else {}
        mapping = link['physicalMapping']
        keys = [f'r.key_{i} AS key{i}' for i in range(len(mapping['edgeIdColumns']))]
        props = ['r.'+name(p)+' AS '+name('prop_'+p) for p in mapping['properties']]
        statement = 'MATCH (a:'+name(link['source'])+')-[r:'+name(relation)+']->(b:'+name(link['target'])+')'
        conditions=[]
        if kind:
            roots = [alias+'.id=$id' for alias, typ in [('a',link['source']),('b',link['target'])] if typ == kind]
            conditions.append('('+' OR '.join(roots)+')')
        # Daily history has millions of rows. Traverse security partitions without
        # silently replacing all history with a date sample or sorting the full view.
        partitioned = link['source']=='DailyBar' and not kind
        if partitioned:
            securities=run('MATCH (n:'+name(link['target'])+') RETURN n.id AS id ORDER BY n.id SKIP '+str(position['partition'])+' LIMIT 1',{})
            if not securities:
                offsets[relation]=None
                continue
            params['instrument']=securities[0]['id']
            conditions.extend(['b.id=$instrument','a.instrumentId=$instrument'])
        elif link['source']=='DailyBar':
            if kind=='DailyBar':
                try: instrument=json.loads(identifier)[0]
                except (ValueError,TypeError,IndexError):raise ValueError('일봉 ID 형식을 확인하세요.') from None
                if not isinstance(instrument,str):raise ValueError('일봉 증권 ID가 필요합니다.')
            else:instrument=identifier
            params['instrument']=instrument
            conditions.append('a.instrumentId=$instrument')
        if conditions:statement+=' WHERE '+' AND '.join(conditions)
        statement += (' RETURN a.id AS sourceId,b.id AS targetId,properties(a) AS source,properties(b) AS target,'+
                      ','.join(keys+props)+' ORDER BY '+','.join(f'key{i}' for i in range(len(keys)))+
                      ' SKIP '+str(offset)+' LIMIT 21')
        rows = run(statement, params)
        for row in rows[:20]:
            a = node(link['source'], {**row['source'], 'id':row['sourceId']})
            b = node(link['target'], {**row['target'], 'id':row['targetId']})
            nodes[a['key']] = a; nodes[b['key']] = b
            identity = normalize([row[f'key{i}'] for i in range(len(keys))])
            edges.append({'key':json.dumps([relation,*identity],ensure_ascii=False,separators=(',',':')),
                          'type':relation,'source':a['key'],'target':b['key'],'identity':identity,
                          'properties':{p:normalize(row['prop_'+p]) for p in mapping['properties']}})
        offsets[relation] = ({'offset':offset+20,'partition':position['partition']} if len(rows)>20 else
                             {'offset':0,'partition':position['partition']+1} if partitioned else None)
    remaining = [key for key,value in offsets.items() if value is not None]
    return {'nodes':list(nodes.values()),'edges':edges,'complete':not remaining,
            'cursor':json.dumps({'scope':[kind,identifier],'offsets':offsets}) if remaining else '',
            'remainingRelations':len(remaining),'relationCount':len(links),
            'checkedAt':datetime.now(timezone.utc).isoformat()}


def normalize(value):
    if isinstance(value,dict):return {k:normalize(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [normalize(v) for v in value]
    if hasattr(value,'iso_format'):return value.iso_format()
    if isinstance(value,(datetime,date)):return value.isoformat()
    return value


def node(kind, properties):
    properties=normalize(properties)
    identifier=properties.get('id')
    if not isinstance(identifier,str) or not identifier:raise RuntimeError('Missing graph object ID')
    label=next((str(properties[k]) for k in ('name','title','segmentName','ticker','tradeDate','eventType') if properties.get(k)),identifier)
    if kind=='ETFHolding':
        weight=properties.get('weightRatio')
        label='보유 비중 '+(format(weight,'.2%') if isinstance(weight,(int,float)) else '미확인')
    return {'key':json.dumps([kind,identifier],ensure_ascii=False,separators=(',',':')),
            'type':kind,'id':identifier,'label':label,'properties':properties}


def search(kind='ETF', query='', run=None):
    if kind not in ROOT_TYPES or not isinstance(query,str) or len(query)>120:
        raise ValueError('ETF·회사·주식·조직 중 검색 대상을 선택하세요. 검색어는 120자 이내입니다.')
    text='MATCH (n:'+name(kind)+')'
    params={'q':query}
    if query:
        terms=['n.id=$q','n.name CONTAINS $q']
        if kind in ('ETF','Equity'):terms.append('n.ticker=$q')
        text+=' WHERE '+' OR '.join(terms)
    text+=' RETURN n.id AS objectId,properties(n) AS properties ORDER BY n.name,n.id LIMIT 41'
    rows=(run or execute)(text,params)
    return {'nodes':[node(kind,{**r['properties'],'id':r['objectId']}) for r in rows[:40]],'truncated':len(rows)>40,
            'limit':40,'checkedAt':datetime.now(timezone.utc).isoformat()}
