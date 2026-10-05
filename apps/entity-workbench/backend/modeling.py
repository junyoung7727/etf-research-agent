"""Editable object definitions over an immutable snapshot; independent of EDGE v1."""
import json
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone


class Conflict(ValueError): pass


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',value):
        raise ValueError('ID는 영문자로 시작하는 영문·숫자·밑줄 64자 이내여야 합니다.')
    return value


def text(value,limit=4000):
    if not isinstance(value,str) or len(value)>limit: raise ValueError('텍스트 길이 또는 형식 오류')


def sources_for(obj,meta):
    sources={'base':obj['table']}
    for join in obj.get('joins',[]):
        alias=identifier(join['id'])
        if alias in sources or join['from'] not in sources: raise ValueError('조인 순서 또는 별칭 오류')
        index=join['fk']
        if type(index)!=int or not 0<=index<len(meta['foreign_keys']): raise ValueError('존재하지 않는 FK')
        if type(join['reverse'])!=bool: raise ValueError('조인 방향 오류')
        fk=meta['foreign_keys'][index]
        if 'definition' in join and join['definition']!=fk: raise ValueError('스냅샷의 FK 정의가 변경되었습니다. 조인 매핑을 다시 검토하세요.')
        origin=fk['target_table' if join['reverse'] else 'table']
        target=fk['table' if join['reverse'] else 'target_table']
        if sources[join['from']]!=origin or target not in meta['schema']: raise ValueError('연결할 수 없는 FK')
        sources[alias]=target
    return sources


def validate_model(model,meta):
    if not isinstance(model,dict) or set(model)!={'objects','relations'}: raise ValueError('객체·관계 목록 필요')
    if any(o.get('formatVersion') == 2 for o in model.get('objects',[]) if isinstance(o,dict)):
        from backend.design_models import model_metadata
        meta=model_metadata(meta)
    if not isinstance(model['objects'],list) or len(model['objects'])>40: raise ValueError('객체는 최대 40개')
    if not isinstance(model['relations'],list) or len(model['relations'])>100: raise ValueError('관계는 최대 100개')
    objects={}
    for obj in model['objects']:
        if not isinstance(obj,dict) or not isinstance(obj.get('joins',[]),list) or not isinstance(obj.get('properties'),list): raise ValueError('객체·조인·속성 형식 오류')
        if any(not isinstance(j,dict) for j in obj.get('joins',[])): raise ValueError('조인 형식 오류')
        key=identifier(obj['id'])
        if key in objects: raise ValueError('중복 객체 ID')
        if obj['table'] not in meta['schema']: raise ValueError('존재하지 않는 기준 테이블')
        keys=obj['key'] if isinstance(obj['key'],list) else [obj['key']]
        if not keys or len(set(keys))!=len(keys) or any(k not in {c['name'] for c in meta['schema'][obj['table']]} for k in keys): raise ValueError('존재하지 않는 식별 열')
        text(obj['label'],200);text(obj.get('note',''))
        if len(obj.get('joins',[]))>8 or len(obj['properties'])>40: raise ValueError('조인 8개·속성 40개 이내')
        sources=sources_for(obj,meta);props={'id'}
        for prop in obj['properties']:
            if not isinstance(prop,dict): raise ValueError('속성 형식 오류')
            field=identifier(prop['id']);text(prop['label'],200)
            if field in props: raise ValueError('중복 속성 ID 또는 예약어 id')
            if prop['source'] not in sources or prop['column'] not in {c['name'] for c in meta['schema'][sources[prop['source']]]}:
                raise ValueError('속성의 원본 매핑 오류')
            props.add(field)
        filters=obj.get('filters',[])
        if not isinstance(filters,list) or len(filters)>10: raise ValueError('필터는 10개 이내')
        for flt in filters:
            if not isinstance(flt,dict): raise ValueError('필터 형식 오류')
            if flt['column'] not in {c['name'] for c in meta['schema'][obj['table']]}: raise ValueError('필터 열 오류')
            values=flt.get('values',[flt.get('value')])
            if flt.get('operator','equals') not in ('equals','in') or not values or len(values)>30: raise ValueError('필터 연산 오류')
            for value in values: text(value,500)
        if 'position' in obj:
            if not isinstance(obj['position'],dict): raise ValueError('카드 위치 오류')
            if any(type(obj['position'].get(k)) not in (int,float) or not -100000<=obj['position'][k]<=100000 for k in ('x','y')): raise ValueError('카드 위치 오류')
        # A designed property can be an endpoint before its source mapping is
        # available. It must remain absent from preview values, not fabricated.
        objects[key]=props | (set(obj.get('propertyDefinitions',{})) if obj.get('formatVersion')==2 else set())
    seen=set()
    for rel in model['relations']:
        if not isinstance(rel,dict): raise ValueError('관계 형식 오류')
        key=identifier(rel['id']);text(rel['label'],200);text(rel.get('note',''))
        if key in seen or key in objects: raise ValueError('중복 관계 또는 객체 ID')
        seen.add(key)
        for side in ('source','target'):
            if rel[side] not in objects or rel[side+'_property'] not in objects[rel[side]]: raise ValueError('관계의 객체 또는 속성이 없습니다.')
        if rel['cardinality'] not in ('1:1','1:N','N:1','N:N'): raise ValueError('관계 개수 정의 오류')
    return model


def read_model(path):
    if not path.exists(): return {'revision':0,'model':{'objects':[],'relations':[]},'saved_at':None}
    with closing(sqlite3.connect(path)) as c:
        row=c.execute('SELECT revision,payload,saved_at FROM model_revision ORDER BY revision DESC LIMIT 1').fetchone()
        return {'revision':row[0],'model':json.loads(row[1]),'saved_at':row[2]} if row else {'revision':0,'model':{'objects':[],'relations':[]},'saved_at':None}


def save_model(path,model,revision,meta):
    validate_model(model,meta)
    if type(revision)!=int or revision<0: raise ValueError('버전 오류')
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path)) as c, c:
        c.execute('CREATE TABLE IF NOT EXISTS model_revision(revision INTEGER PRIMARY KEY,payload TEXT,saved_at TEXT)')
        c.execute('BEGIN IMMEDIATE')
        current=c.execute('SELECT coalesce(max(revision),0) FROM model_revision').fetchone()[0]
        if current!=revision: raise Conflict('다른 창에서 모델을 저장했습니다. JSON으로 내보낸 뒤 다시 불러와 변경을 비교하세요.')
        stamp=datetime.now(timezone.utc).isoformat()
        c.execute('INSERT INTO model_revision VALUES(?,?,?)',(current+1,json.dumps(model,ensure_ascii=False),stamp))
    return {'revision':current+1,'model':model,'saved_at':stamp}


def object_sql(obj,meta):
    sources=sources_for(obj,meta)
    clause=f'FROM "{obj["table"]}" AS "base"'
    for join in obj.get('joins',[]):
        fk=meta['foreign_keys'][join['fk']];reverse=join['reverse']
        left=fk['target_columns' if reverse else 'columns'];right=fk['columns' if reverse else 'target_columns']
        condition=' AND '.join(f'"{join["from"]}"."{a}"="{join["id"]}"."{b}"' for a,b in zip(left,right))
        # Materialize the read-only source so SQLite can build a composite join index.
        # The snapshot's single-column type indexes otherwise trigger repeated full type scans.
        clause+=f' LEFT JOIN (SELECT rowid AS "__model_rowid",* FROM "{sources[join["id"]]}" LIMIT -1 OFFSET 0) AS "{join["id"]}" ON {condition}'
    keys=obj['key'] if isinstance(obj['key'],list) else [obj['key']]
    if len(keys)>1:
        missing=' OR '.join(f'"base"."{k}" IS NULL' for k in keys)
        parts=','.join(f'CAST("base"."{k}" AS TEXT)' for k in keys)
        identity=f'CASE WHEN {missing} THEN NULL ELSE json_array({parts}) END'
    else: identity=f'"base"."{keys[0]}"'
    values={'id':identity}
    values.update({p['id']:('NULL' if p.get('mappingStatus')=='needsCorrection' else f'"{p["source"]}"."{p["column"]}"') for p in obj['properties']})
    for prop in obj['properties']:
        if 'valueMapping' in prop and prop.get('mappingStatus')!='needsCorrection':
            # Normalize before filtering so a search for FY finds annual reports
            # stored under the provider's Q4 code. Raw source columns stay intact.
            literal=lambda value: 'NULL' if value is None else "'"+value.replace("'","''")+"'"
            cases=' '.join('WHEN '+literal(k)+' THEN '+literal(v) for k,v in prop['valueMapping'].items())
            values[prop['id']]='CASE '+values[prop['id']]+' '+cases+' ELSE NULL END'
    filters=obj.get('filters',[])
    clauses=[];args=[]
    for f in filters:
        vals=f.get('values',[f.get('value')]);args.extend(vals)
        clauses.append(f'"base"."{f["column"]}" IN ('+','.join('?' for _ in vals)+')')
    where=(' WHERE '+' AND '.join(clauses)) if clauses else ''
    return sources,clause,values,where,args


def preview_object(path,model,object_id,search=''):
    text(search,500)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        deadline=time.monotonic()+10
        c.set_progress_handler(lambda: int(time.monotonic()>deadline),10000)
        meta=json.loads(c.execute('SELECT payload FROM _metadata').fetchone()[0]);validate_model(model,meta)
        obj=next((o for o in model['objects'] if o['id']==object_id),None)
        if not obj: raise ValueError('객체 없음')
        if obj.get('formatVersion')==2:
            from backend.design_models import model_metadata
            snapshot_tables=set(meta['schema'])
            meta=model_metadata(meta)
            absent=set(sources_for(obj,meta).values())-snapshot_tables
            if absent: raise ValueError('로컬 스냅샷에 미수집된 원본 테이블: '+', '.join(sorted(absent)))
        sources,clause,values,where,args=object_sql(obj,meta)
        key=values['id']
        base=c.execute(f'SELECT count(*) FROM "{obj["table"]}" AS "base"'+where,args).fetchone()[0]
        total,nulls=c.execute(f'SELECT count(*),coalesce(sum({key} IS NULL),0) '+clause+where,args).fetchone()
        duplicates=c.execute(f'SELECT count(*) FROM (SELECT {key} '+clause+where+f' GROUP BY {key} HAVING count(*)>1 AND {key} IS NOT NULL)',args).fetchone()[0]
        missing={alias:c.execute(f'SELECT count(*) '+clause+where+(' AND ' if where else ' WHERE ')+f'"{alias}"."__model_rowid" IS NULL',args).fetchone()[0] for alias in sources if alias!='base'}
        selected=[f'{expression} AS "{name}"' for name,expression in values.items()]
        source_fields=[(alias,col['name']) for alias,table in sources.items() for col in meta['schema'][table]]
        selected += [f'"{alias}"."{column}"' for alias,column in source_fields]
        if search:
            literal=search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            where+=(' AND ' if where else ' WHERE ')+'('+' OR '.join(f"CAST({v} AS TEXT) LIKE ? ESCAPE '\\'" for v in values.values())+')'
            args=args+['%'+literal+'%']*len(values)
        raw=c.execute('SELECT '+','.join(selected)+' '+clause+where+f' ORDER BY {key} LIMIT 21',args).fetchall()
        rows=[]
        for row in raw[:20]:
            provenance={alias:{} for alias in sources}
            for (alias,col),value in zip(source_fields,row[len(values):]): provenance[alias][col]=value
            mapped=dict(zip(values,row[:len(values)]))
            for p in obj['properties']:
                if 'lookup' in p:
                    lookup=p['lookup'];mapped[p['id']]=lookup['values'].get(str(mapped[p['id']]),lookup.get('default'))
            rows.append({'values':mapped,'sources':provenance})
        return {'rows':rows,'truncated':len(raw)>20,'stats':{'base_rows':base,'joined_rows':total,'null_ids':nulls,'duplicate_ids':duplicates,'missing_joins':missing},
                'viewOnlyProperties':obj.get('preview',{}).get('viewOnlyProperties',[]),
                'sources':sources,'partial_tables':[t for t in set(sources.values()) if not meta['tables'].get(t,{}).get('complete',False)],
                'scope':'통계는 검색 전 전체 스냅샷 기준 · 미리보기 최대 20행 · 중복 제거 없음'}
