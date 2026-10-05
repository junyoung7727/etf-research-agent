"""Local entity inspection: immutable AWS snapshots and separate review history."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from backend.modeling import read_model, preview_object, save_model
from backend.value_types import read_catalog as read_value_catalog, save_catalog as save_value_catalog, promote_catalog as promote_value_catalog, RevisionConflict, SourceConflict
from backend.definition_sources import source_state, promote_definitions
from backend.yaml_models import load_models
from backend.view_design import read_catalog as read_view_design
from backend.interface_types import read_catalog as read_interfaces, save_catalog as save_interfaces, promote_catalog as promote_interfaces

from paths import ROOT, APP as HERE, DATA, FRONTEND, METADATA, EDGE_ONTOLOGY
from ontology.oms.loader import definition_files

TABLES = ('entity','actor','company_profile','instrument','equity_profile','etf_profile',
          'document','document_entity','disclosure_document','disclosure_fact',
          'business_segment_fact','supply_contract_fact','source_event','event_argument','etf_holding_snapshot','concept','market_series')
LOCK = threading.RLock()
STATE = {'refreshing': False, 'error': None}


def current_model():
    library = EDGE_ONTOLOGY / 'metadata'
    sources = source_state(METADATA, library)
    files = definition_files(METADATA, library)
    saved = read_model(DATA / 'models.sqlite3')
    expected = {k: v for obj in saved['model']['objects'] for k, v in obj.get('definitionSources', {}).items()}
    if files != expected:
        meta = metadata(DATA / 'snapshot.sqlite3')
        model = load_models(METADATA / 'object_types', meta, library)
        model['objects'].sort(key=lambda o: (o.get('group', ''), o['id']))
        saved = save_model(DATA / 'models.sqlite3', model, saved['revision'], meta)
    saved.update(yaml_matches=True, definitionSources=sources,
                 checked_at=datetime.now(timezone.utc).isoformat())
    return saved


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode()).hexdigest()


def matches_fk(left, right, fk):
    return all(left.get(a) is not None and left.get(a)==right.get(b) for a,b in zip(fk['columns'],fk['target_columns']))


def relationship(left, right, fk):
    values=[left['row'][k] for k in fk['columns']]
    return {'source':left.get('id'),'target':right.get('id'),'label':'+'.join(fk['columns']),
            'edge_key':fk['table']+'.'+'+'.join(fk['columns'])+':'+json.dumps(values,ensure_ascii=False,separators=(',',':'))+'->'+fk['target_table'],
            'evidence_hash':fingerprint([left['row'],right['row']]),'kind':'FK','left':left,'right':right}


def resolve_fk(path, table, column, row):
    meta=metadata(path)
    fk=next((f for f in meta['foreign_keys'] if f['table']==table and column in f['columns']),None)
    if not fk or fk['target_table'] not in TABLES: raise ValueError('수집 범위 밖의 FK')
    with connect(path) as c:
        where=' AND '.join(f'"{k}"=?' for k in fk['target_columns'])
        values=[row.get(k) for k in fk['columns']]
        target=c.execute(f'SELECT * FROM "{fk["target_table"]}" WHERE '+where,values).fetchone()
        if not target: return {'missing':True}
        return relationship({'table':table,'row':row},{'table':fk['target_table'],'row':dict(target)},fk)


@contextmanager
def connect(path):
    conn = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    def numeric_compare(a,b):
        try:
            x,y=Decimal(a),Decimal(b)
            return (x>y)-(x<y)
        except InvalidOperation: return (a>b)-(a<b)
    conn.create_collation('EXACT_NUMERIC',numeric_compare)
    try: yield conn
    finally: conn.close()


def browse(path, table, search='', sort='', direction='asc', limit=50, offset=0, field='', value=''):
    if table not in TABLES:
        raise ValueError('허용되지 않은 테이블')
    with connect(path) as c:
        cols = [r[1] for r in c.execute(f'PRAGMA table_info("{table}")')]
        if not cols or (sort and sort not in cols) or (field and field not in cols):
            raise ValueError('유효하지 않은 열')
        if direction not in ('asc','desc') or not 1 <= int(limit) <= 100 or int(offset) < 0:
            raise ValueError('유효하지 않은 페이지')
        predicates, args = [], []
        if search:
            predicates.append('('+' OR '.join(f'CAST("{x}" AS TEXT) LIKE ? ESCAPE \'\\\'' for x in cols)+')')
            literal = search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            args += ['%'+literal+'%'] * len(cols)
        if field:
            predicates.append(f'"{field}" = ?')
            args.append(value)
        where = ' WHERE '+' AND '.join(predicates) if predicates else ''
        total = c.execute(f'SELECT count(*) FROM "{table}"'+where,args).fetchone()[0]
        chosen=sort or cols[0]
        schema=[]
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='_metadata'").fetchone():
            schema=json.loads(c.execute('SELECT payload FROM _metadata').fetchone()[0]).get('schema',{}).get(table,[])
        numeric=any(x['name']==chosen and x['type'] in ('numeric','bigint') for x in schema)
        order = f' ORDER BY "{chosen}"'+(' COLLATE EXACT_NUMERIC' if numeric else '')+f' {direction}, rowid'
        rows = [dict(r) for r in c.execute(f'SELECT * FROM "{table}"'+where+order+' LIMIT ? OFFSET ?',args+[int(limit),int(offset)])]
        return {'columns':cols,'rows':rows,'total':total,'offset':int(offset),'limit':int(limit)}


def entity_catalog(path, kind='COMPANY'):
    # A lightweight complete identity list, independent of the paginated row inspector.
    joins={'COMPANY':'JOIN company_profile p ON p.actor_id=e.entity_id',
           'EQUITY':'JOIN equity_profile p ON p.instrument_id=e.entity_id',
           'ETF':'JOIN etf_profile p ON p.instrument_id=e.entity_id'}
    if kind not in (*joins,'ACTOR','INSTRUMENT','CONCEPT'):
        raise ValueError('지원하지 않는 엔티티 타입')
    sql='SELECT e.entity_id,e.display_name,e.entity_type FROM entity e '
    params=()
    if kind in joins: sql+=joins[kind]
    else: sql+='WHERE e.entity_type=?';params=(kind,)
    with connect(path) as c:
        rows=[dict(r) for r in c.execute(sql+' ORDER BY e.display_name,e.entity_id',params)]
    return {'kind':kind,'total':len(rows),'rows':rows}


def save_review(path, data):
    if data.get('status') not in ('confirmed','rejected','needs_review'):
        raise ValueError('검증 상태 오류')
    if not isinstance(data.get('edge_key'),str) or not 1 <= len(data['edge_key']) <= 500:
        raise ValueError('연결 키 오류')
    if not isinstance(data.get('evidence_hash'),str) or len(data['evidence_hash']) != 64:
        raise ValueError('근거 버전 오류')
    if not isinstance(data.get('note',''),str) or len(data.get('note','')) > 4000:
        raise ValueError('메모는 4,000자 이내')
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path)) as c, c:
        c.execute('CREATE TABLE IF NOT EXISTS review(id INTEGER PRIMARY KEY, edge_key TEXT, evidence_hash TEXT, status TEXT, note TEXT, recorded_at TEXT)')
        c.execute('INSERT INTO review(edge_key,evidence_hash,status,note,recorded_at) VALUES(?,?,?,?,?)',
                  (data['edge_key'],data['evidence_hash'],data['status'],data.get('note',''),datetime.now(timezone.utc).isoformat()))


def read_reviews(path):
    if not path.exists(): return []
    with connect(path) as c:
        return [dict(r) for r in c.execute('SELECT * FROM review ORDER BY id DESC')]


def capture():
    DATA.mkdir(parents=True,exist_ok=True)
    temp = DATA / f'snapshot-{secrets.token_hex(6)}.sqlite3'
    spec=importlib.util.spec_from_file_location('entity_source', ROOT/'apps/news-research/source.py')
    source=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    meta={'tables':{},'schema':{},'foreign_keys':[],'aliases':[]}
    try:
        with source.open_source(profile='work') as reader, closing(sqlite3.connect(temp)) as local, local:
            pg=reader.connection
            with pg.cursor() as cur:
                cur.execute("SELECT current_user,current_setting('transaction_read_only'),transaction_timestamp()")
                role, readonly, stamp=cur.fetchone()
                if (role,readonly)!=('agent_ro','on'): raise RuntimeError('Read-only verification failed')
                meta.update(captured_at=stamp.isoformat(),role=role,source='AWS work / edge-dev / edge',mode='read-only snapshot')
                cur.execute("SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(%s) ORDER BY table_name,ordinal_position",(list(TABLES),))
                for table,col,typ in cur.fetchall(): meta['schema'].setdefault(table,[]).append({'name':col,'type':typ})
                cur.execute("SELECT cl.relname,a.attname,cr.relname,b.attname,co.conname FROM pg_constraint co JOIN pg_class cl ON cl.oid=co.conrelid JOIN pg_class cr ON cr.oid=co.confrelid JOIN LATERAL unnest(co.conkey,co.confkey) WITH ORDINALITY AS k(l,r,n) ON true JOIN pg_attribute a ON a.attrelid=cl.oid AND a.attnum=k.l JOIN pg_attribute b ON b.attrelid=cr.oid AND b.attnum=k.r WHERE co.contype='f' AND cl.relnamespace='public'::regnamespace AND cl.relname=ANY(%s) ORDER BY cl.relname,co.conname,k.n",(list(TABLES),))
                constraints={}
                for tab,col,target,target_col,name in cur.fetchall():
                    f=constraints.setdefault((tab,name),{'table':tab,'column':col,'target_table':target,'target_column':target_col,'constraint':name,'columns':[],'target_columns':[]})
                    f['columns'].append(col);f['target_columns'].append(target_col)
                meta['foreign_keys']=list(constraints.values())
            for table in TABLES:
                cols=meta['schema'][table]
                types=['INTEGER' if x['type'] in ('integer','smallint') else 'REAL' if x['type'] in ('double precision','real') else 'TEXT' for x in cols]
                local.execute(f'CREATE TABLE "{table}" ('+','.join(f'"{x["name"]}" {t}' for x,t in zip(cols,types))+')')
                scope='전체'
                sql=f'SELECT * FROM public."{table}"'
                params=()
                if table=='document':
                    sql+=' WHERE document_id IN (SELECT document_id FROM document ORDER BY available_at DESC,document_id LIMIT 3000) OR document_id IN (SELECT document_id FROM disclosure_document)'; scope='최근 3,000개 문서 + 수집 공시 전체'
                elif table=='document_entity':
                    sql+=' WHERE document_id IN (SELECT document_id FROM document ORDER BY available_at DESC,document_id LIMIT 3000)';scope='최근 3,000개 문서의 연결'
                elif table=='source_event':
                    sql+=' ORDER BY available_at DESC,source_event_id LIMIT 1500';scope='최근 1,500개 사건'
                elif table=='event_argument':
                    sql+=' WHERE source_event_id IN (SELECT source_event_id FROM source_event ORDER BY available_at DESC,source_event_id LIMIT 1500)';scope='최근 1,500개 사건의 인자'
                elif table=='etf_holding_snapshot':
                    sql+=' WHERE (etf_instrument_id,trade_date) IN (SELECT etf_instrument_id,max(trade_date) FROM etf_holding_snapshot GROUP BY etf_instrument_id)';scope='ETF별 최신 편입일'
                with pg.cursor() as cur:
                    cur.execute(f'SELECT count(*) FROM public."{table}"'); total=cur.fetchone()[0]
                    cur.execute(sql,params)
                    count=0
                    while True:
                        rows=cur.fetchmany(2000)
                        if not rows: break
                        normalized=[[None if v is None else v if isinstance(v,(str,int,float)) else str(v) for v in row] for row in rows]
                        local.executemany(f'INSERT INTO "{table}" VALUES ('+','.join('?' for _ in cols)+')',normalized)
                        count+=len(rows)
                    meta['tables'][table]={'loaded':count,'source_total':total,'scope':scope,'complete':count==total}
                    print(f'{table}: {count}/{total}',flush=True)
                for col in cols:
                    if col['name'].endswith('_id') or col['name'] in ('ticker','dart_corp_code','entity_type','actor_type'):
                        local.execute(f'CREATE INDEX "ix_{table}_{col["name"]}" ON "{table}"("{col["name"]}")')
            alias_path=Path('D:/Github/edge/src/apps/cloud/data-pipeline/src/data_pipeline/entity_resolution.py')
            if alias_path.exists():
                body=alias_path.read_text(encoding='utf-8')
                for node in ast.walk(ast.parse(body)):
                    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_INSTRUMENT_ALIASES' for t in node.targets):
                        meta['aliases']=[{'alias':a,'target_name':b,'provenance':'EDGE 코드 사전 · DB 행 아님'} for a,b in ast.literal_eval(node.value).items()]
                meta['alias_source_hash']=hashlib.sha256(body.encode()).hexdigest()
            local.execute('CREATE TABLE _metadata(payload TEXT)')
            local.execute('INSERT INTO _metadata VALUES(?)',(json.dumps(meta,ensure_ascii=False),))
        # Publish only after remote context cleanup and local commit both succeed.
        with LOCK: os.replace(temp,DATA/'snapshot.sqlite3')
    finally:
        if temp.exists(): temp.unlink()


def metadata(path):
    with connect(path) as c: return json.loads(c.execute('SELECT payload FROM _metadata').fetchone()[0])


def entity_detail(path, identifier):
    nodes,edges=[],[]
    with connect(path) as c:
        def add(table,field,value):
            rows=[dict(r) for r in c.execute(f'SELECT * FROM "{table}" WHERE "{field}"=?', (value,))]
            for row in rows:
                key=table+':'+fingerprint(row)[:16]
                if not any(n['id']==key for n in nodes): nodes.append({'id':key,'table':table,'row':row})
            return [n for n in nodes if n['table']==table and n['row'].get(field)==value]
        entity=add('entity','entity_id',identifier)
        if not entity: raise ValueError('엔티티를 찾을 수 없음')
        add('actor','actor_id',identifier)
        add('company_profile','actor_id',identifier)
        add('instrument','instrument_id',identifier)
        add('etf_profile','instrument_id',identifier)
        add('concept','concept_id',identifier)
        equities=add('equity_profile','instrument_id',identifier)
        equities+=add('equity_profile','issuer_actor_id',identifier)
        for n in equities:
            r=n['row']
            add('instrument','instrument_id',r['instrument_id'])
            add('entity','entity_id',r['instrument_id'])
            add('company_profile','actor_id',r['issuer_actor_id'])
            add('actor','actor_id',r['issuer_actor_id'])
            add('entity','entity_id',r['issuer_actor_id'])
        meta=metadata(path)
        for fk in meta['foreign_keys']:
            for a in [n for n in nodes if n['table']==fk['table']]:
                for b in [n for n in nodes if n['table']==fk['target_table']]:
                    if matches_fk(a['row'],b['row'],fk):
                        edges.append(relationship(a,b,fk))
        actor_id=identifier if entity[0]['row']['entity_type']=='ACTOR' else (equities[0]['row']['issuer_actor_id'] if equities else None)
        documents=[]
        if actor_id:
            documents=[dict(r) for r in c.execute('''SELECT DISTINCT d.*, '기존 종목 연결의 기업 투영' AS relation_kind FROM document d
                JOIN document_entity de ON de.document_id=d.document_id JOIN equity_profile ep ON ep.instrument_id=de.entity_id
                WHERE ep.issuer_actor_id=? UNION SELECT d.*, '직접 공시' FROM document d JOIN disclosure_document dd ON dd.document_id=d.document_id
                WHERE dd.issuer_actor_id=? LIMIT 100''',(actor_id,actor_id))]
        return {'nodes':nodes,'edges':edges,'documents':documents,'documents_scope':'수집된 문서 범위 안 · 최대 100행','actor_id':actor_id}


def row_connections(path, table, row):
    """All inbound and outbound one-hop FKs of an exact stored row, never inferred links."""
    if table not in TABLES or not isinstance(row,dict) or not row:
        raise ValueError('잘못된 행')
    meta=metadata(path)
    with connect(path) as c:
        columns={r[1] for r in c.execute(f'PRAGMA table_info("{table}")')}
        if set(row)!=columns: raise ValueError('전체 원본 행 필요')
        where=' AND '.join(f'"{k}" IS ?' for k in row)
        stored=c.execute(f'SELECT * FROM "{table}" WHERE '+where,list(row.values())).fetchone()
        if not stored: raise ValueError('원본 행 없음')
        def node(tab,record):
            record=dict(record)
            return {'id':tab+':'+fingerprint(record)[:16],'table':tab,'row':record}
        root=node(table,stored);nodes={root['id']:root};edges={};missing=[]
        for fk in meta['foreign_keys']:
            for outgoing in (True,False):
                if table!=fk['table' if outgoing else 'target_table']: continue
                target=fk['target_table' if outgoing else 'table']
                if target not in TABLES:
                    missing.append({'table':target,'reason':'수집 범위 밖'});continue
                source_cols=fk['columns' if outgoing else 'target_columns']
                target_cols=fk['target_columns' if outgoing else 'columns']
                values=[row[k] for k in source_cols]
                if any(v is None for v in values): continue
                predicate=' AND '.join(f'"{k}"=?' for k in target_cols)
                matches=c.execute(f'SELECT * FROM "{target}" WHERE '+predicate,values).fetchall()
                if outgoing and not matches: missing.append({'table':target,'reason':'스냅샷에 대상 없음'})
                for record in matches:
                    other=node(target,record);nodes[other['id']]=other
                    edge=relationship(root,other,fk) if outgoing else relationship(other,root,fk)
                    edges[(edge['source'],edge['target'],edge['label'])]=edge
        return {'nodes':list(nodes.values()),'edges':list(edges.values()),'root_id':root['id'],
                'missing':missing,'scope':'스냅샷 내 직접 FK 전체 · 들어오는 연결 + 나가는 연결 · 더블클릭으로 다음 연결 확장',
                'partial_tables':[t for t,v in meta.get('tables',{}).items() if not v.get('complete',False)]}


class Handler(BaseHTTPRequestHandler):
    token = secrets.token_urlsafe(32)

    def log_message(self,*args): pass

    def reply(self,status,payload,typ='application/json; charset=utf-8'):
        data=json.dumps(payload,ensure_ascii=False,default=str).encode() if not isinstance(payload,bytes) else payload
        self.send_response(status); self.send_header('Content-Type',typ)
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers();self.wfile.write(data)

    def safe_host(self):
        return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.safe_host(): return self.reply(403,{'error':'Local host only'})
        u=urlparse(self.path);q={k:v[0] for k,v in parse_qs(u.query).items()}
        try:
            if u.path.startswith('/api/puppygraph/'):
                from backend import puppygraph_viewer as viewer
                if u.path=='/api/puppygraph/catalog': return self.reply(200,viewer.catalog())
                if u.path=='/api/puppygraph/search': return self.reply(200,viewer.search(**q))
                if u.path=='/api/puppygraph/connections': return self.reply(200,viewer.connections(**q))
                return self.reply(404,{'error':'Not found'})
            with LOCK:
                path=DATA/'snapshot.sqlite3'
                if u.path=='/api/status': return self.reply(200,{**STATE,'ready':path.exists(),'token':self.token})
                if u.path=='/api/value-types': return self.reply(200,read_value_catalog(DATA/'value-types.sqlite3'))
                if u.path=='/api/interfaces': return self.reply(200,read_interfaces(DATA/'interfaces.sqlite3',EDGE_ONTOLOGY/'metadata',METADATA))
                if u.path=='/api/meta': return self.reply(200,metadata(path))
                if u.path=='/api/model':
                    return self.reply(200,current_model())
                if u.path=='/api/view-design': return self.reply(200,read_view_design())
                if u.path=='/api/rows': return self.reply(200,browse(path,**q))
                if u.path=='/api/catalog': return self.reply(200,entity_catalog(path,**q))
                if u.path=='/api/entity': return self.reply(200,entity_detail(path,q['id']))
                if u.path=='/api/connections': return self.reply(200,row_connections(path,q['table'],json.loads(q['row'])))
                if u.path=='/api/fk': return self.reply(200,resolve_fk(path,q['table'],q['column'],json.loads(q['row'])))
                if u.path=='/api/reviews': return self.reply(200,read_reviews(DATA/'reviews.sqlite3'))
                files={'/':'entities/index.html','/app.js':'entities/app.js','/style.css':'entities/style.css','/collection.css':'entities/collection.css','/graph-layout.mjs':'entities/graph-layout.mjs','/modeler':'objects/modeler.html','/modeler.js':'objects/modeler.js','/modeler.css':'objects/modeler.css','/model-layout.mjs':'objects/model-layout.mjs','/vendor/elk.bundled.js':'vendor/elk.bundled.js'}
                files.update({'/value-types':'value_types/value-types.html','/value-types.js':'value_types/value-types.js','/value-types.css':'value_types/value-types.css'})
                files.update({'/interfaces':'value_types/interfaces.html','/interfaces.js':'value_types/interfaces.js','/interfaces.css':'value_types/interfaces.css'})
                files.update({'/view-design':'view_design/index.html','/view-design.js':'view_design/app.js','/view-design.css':'view_design/style.css'})
                files.update({'/puppygraph':'puppygraph/index.html','/puppygraph.js':'puppygraph/app.js','/puppygraph.css':'puppygraph/style.css'})
                files.update({'/puppygraph-exploration.js':'puppygraph/exploration.js','/vendor/vis-network.min.js':'vendor/vis-network.min.js'})
                if u.path in files:
                    f=FRONTEND/files[u.path];types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css'}
                    return self.reply(200,f.read_bytes(),types[f.suffix]+'; charset=utf-8')
                self.reply(404,{'error':'Not found'})
        except (ValueError,KeyError,TypeError) as exc: self.reply(400,{'error':str(exc) if u.path.startswith('/api/puppygraph/') or u.path in ('/api/value-types','/api/interfaces','/api/model','/api/view-design') else '잘못된 조회 조건입니다.'})
        except Exception: self.reply(503,{'error':'PuppyGraph에 연결할 수 없습니다. 클라우드 태스크·AWS 로그인·SSM 연결을 확인한 뒤 다시 조회하세요.' if u.path.startswith('/api/puppygraph/') else '스냅샷 조회 실패. 새로 수집하거나 서버 로그를 확인하세요.'})

    def do_POST(self):
        if not self.safe_host() or self.headers.get('X-Workbench-Token')!=self.token:
            return self.reply(403,{'error':'Local request token required'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0 < size <= (2000000 if self.path in ('/api/value-types','/api/interfaces') else 256000 if self.path.startswith('/api/model') else 16000): raise ValueError()
            data=json.loads(self.rfile.read(size))
            if self.path=='/api/interfaces':
                with LOCK:
                    result=save_interfaces(DATA/'interfaces.sqlite3',data['catalog'],data['revision'],data['sourceHash'],EDGE_ONTOLOGY/'metadata',METADATA)
                return self.reply(200,result)
            if self.path=='/api/interfaces/apply':
                with LOCK:
                    result=promote_interfaces(DATA/'interfaces.sqlite3',data['revision'],data['sourceHash'],EDGE_ONTOLOGY/'metadata',METADATA)
                return self.reply(200,result)
            if self.path=='/api/value-types/apply':
                with LOCK:
                    result=promote_value_catalog(DATA/'value-types.sqlite3',data['revision'],data['sourceHash'])
                return self.reply(200,result)
            if self.path=='/api/model/apply':
                with LOCK:
                    library=EDGE_ONTOLOGY/'metadata'
                    meta=metadata(DATA/'snapshot.sqlite3')
                    promote_definitions(METADATA,library,data['sourceHash'],
                        validate=lambda: load_models(METADATA/'object_types',meta,library))
                    result=current_model()
                return self.reply(200,result)
            if self.path=='/api/value-types':
                with LOCK:
                    result=save_value_catalog(DATA/'value-types.sqlite3',data['catalog'],data['revision'],data['sourceHash'])
                return self.reply(200,result)
            if self.path=='/api/model': return self.reply(405,{'error':'모델 조회 전용 화면입니다. 저장 API는 비활성화했습니다.'})
            if self.path=='/api/model/preview':
                with LOCK:
                    snapshot=DATA/'snapshot.sqlite3'
                    saved=current_model()
                    if data.get('revision')!=saved['revision']:
                        return self.reply(409,{'error':'발행 버전이 바뀌었습니다. 최신 확인 후 다시 조회하세요.'})
                    result=preview_object(snapshot,saved['model'],data['object_id'],data.get('search',''))
                return self.reply(200,result)
            if self.path=='/api/reviews':
                save_review(DATA/'reviews.sqlite3',data);return self.reply(200,{'saved':True})
            if self.path=='/api/refresh':
                with LOCK:
                    if STATE['refreshing']: return self.reply(409,{'error':'이미 수집 중입니다.'})
                    STATE.update(refreshing=True,error=None)
                def run():
                    try: capture()
                    except Exception as e: STATE['error']='수집 실패: '+type(e).__name__+'. 기존 스냅샷을 유지합니다.'
                    finally: STATE['refreshing']=False
                threading.Thread(target=run,daemon=True).start()
                return self.reply(202,{'started':True})
            self.reply(404,{'error':'Not found'})
        except (RevisionConflict,SourceConflict) as exc: self.reply(409,{'error':str(exc)})
        except (ValueError,TypeError,KeyError) as exc: self.reply(400,{'error':str(exc) if self.path.startswith(('/api/model','/api/value-types','/api/interfaces')) else '저장 형식을 확인하세요.'})
        except OSError as exc: self.reply(503,{'error':'파일 반영 실패: '+str(exc)})
        except sqlite3.OperationalError: self.reply(503,{'error':'조회 제한 시간 또는 스냅샷 조건을 확인하세요. 조인 수를 줄여 다시 시도하세요.'})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--capture',action='store_true');parser.add_argument('--port',type=int,default=5186)
    args=parser.parse_args()
    if args.capture: capture()
    else:
        print(f'Entity workbench: http://127.0.0.1:{args.port}',flush=True)
        ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
