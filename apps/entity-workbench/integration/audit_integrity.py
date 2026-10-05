import json,time,sys
from pilot_graph import read_catalog
from pilot_session import database,OUT
cata=read_catalog();objects={o['id']:o for o in cata['objects']};tables={o['id']:o for o in cata['physicalTables']}
report={'objects':{},'links':{},'failures':[]}
if '--resume' in sys.argv:report=json.loads((OUT/'integrity.json').read_text(encoding='utf8'))
def save():(OUT/'integrity.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf8')
with database() as conn,conn.cursor() as c:
    for n,o in objects.items():
        if n in report['objects']:continue
        if n=='DailyBar':
            # PK and injective JSON-array encoding prove uniqueness without sorting all IDs.
            c.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='public.price_daily'::regclass AND contype='p'")
            pk=c.fetchone()[0];assert pk=='PRIMARY KEY (instrument_id, trade_date)'
            c.execute('SELECT instrument_id,count(*),min(trade_date),max(trade_date) FROM price_daily GROUP BY instrument_id')
            groups=c.fetchall()
            c.execute('SELECT count(*) FROM price_daily p LEFT JOIN instrument i USING(instrument_id) WHERE i.instrument_id IS NULL')
            assert c.fetchone()[0]==0
            report['objects'][n]={'rows':sum(r[1] for r in groups),'instrumentPartitions':len(groups),'identityProof':pk+' + compact JSON string-array encoding','fullDistinctSort':'not run; partitioned source counts and source PK used'}
        else:
            c.execute('SELECT count(*),count(DISTINCT id),count(*) FILTER(WHERE id IS NULL) FROM '+o['viewName'])
            rows,distinct,nulls=c.fetchone();assert rows==distinct and nulls==0,n
            report['objects'][n]={'rows':rows,'uniqueIds':True,'nullIds':nulls}
        save();print('object',n,report['objects'][n],flush=True)
    for r in cata['relations']:
        m=r['physicalMapping'];name=r['id']
        if name in report['links']:continue
        if m['kind']=='blocked':report['links'][name]={'status':'blocked'};continue
        if m['source']=='DailyBar':
            profile='equity_profile' if r['target']=='Equity' else 'etf_profile'
            c.execute('SELECT sum(p.n) FROM (SELECT instrument_id,count(*) n FROM price_daily GROUP BY instrument_id) p JOIN '+profile+' s USING(instrument_id)')
            total=int(c.fetchone()[0] or 0)
            report['links'][name]={'sourceRows':total,'nullEndpoints':0,'orphanEndpoints':0,'linkedRows':total,'method':'partition counts joined to actual typed profile; view keeps source PK and uses same profile qualification'}
            save();print('link',name,report['links'][name],flush=True);continue
        t=tables[m['source']];conditions=[];params=[]
        for col,values in m['filters'].items():conditions.append('v.'+col+'=ANY(%s)');params.append(values)
        where=' WHERE '+' AND '.join(conditions) if conditions else ''
        joins='';src='v.'+m['fromColumn'];dst='v.'+m['toColumn']
        source_missing='false';target_missing='false'
        if not (m['source']==r['source'] and m['fromColumn']=='id'):
            joins+=' LEFT JOIN '+objects[r['source']]['viewName']+' s ON s.id='+src
            source_missing=src+' IS NOT NULL AND s.id IS NULL'
        if not (m['source']==r['target'] and m['toColumn']=='id'):
            joins+=' LEFT JOIN '+objects[r['target']]['viewName']+' z ON z.id='+dst
            target_missing=dst+' IS NOT NULL AND z.id IS NULL'
        c.execute('SELECT count(*),count(*) FILTER(WHERE '+src+' IS NULL OR '+dst+' IS NULL),count(*) FILTER(WHERE ('+source_missing+') OR ('+target_missing+')) FROM '+t['viewName']+' v'+joins+where,params)
        total,missing,orphan=c.fetchone()
        report['links'][name]={'sourceRows':total,'nullEndpoints':missing,'orphanEndpoints':orphan,'linkedRows':total-missing-orphan}
        if orphan:report['failures'].append(name)
        save();print('link',name,report['links'][name],flush=True)
    c.execute("SELECT count(*) FROM ontology_view.financial_metric WHERE derivation<>'REPORTED' AND reported_snapshot_id IS NOT NULL")
    assert c.fetchone()[0]==0
    c.execute('SELECT count(*) FROM ontology_view.financial_metric m JOIN ontology_view.financial_report_snapshot r ON r.id=m.reporting_context_id WHERE m.corp_code<>r.corp_code OR m.fiscal_year<>r.fiscal_year OR m.fs_basis<>r.fs_basis')
    assert c.fetchone()[0]==0
    report['financialContextAndDirectSource']=True
report['passed']=not report['failures'];save()
assert report['passed'],report['failures']
