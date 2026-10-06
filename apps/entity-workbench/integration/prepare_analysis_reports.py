"""Expose published v2 analysis documents through ETF links, excluding operational runs."""
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime,timezone
import yaml

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from paths import METADATA,EDGE_ONTOLOGY
from integration.pilot_session import database
from ontology.oms.loader import read_definitions
from backend.view_design import read_catalog


def prepare():
    schema_path=APP/'data/source-schema.json';schema=json.loads(schema_path.read_text(encoding='utf8'))
    plan_path=APP/'data/view-design.json';plan=json.loads(plan_path.read_text(encoding='utf8'))
    with database() as db,db.cursor() as cursor:
        for category,kind in [('outlook','ETFOutlookReport'),('movement','ETFPriceExplanation')]:
            table=category+'_analyses';view='etf_'+('outlook_report' if category=='outlook' else 'price_explanation')
            cursor.execute("SELECT column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",(table,))
            schema['schema'][table]=[{'name':n,'type':t,'nullable':nullable=='YES','default':default} for n,t,nullable,default in cursor.fetchall()]
            cursor.execute("SELECT a.attname FROM pg_constraint p CROSS JOIN LATERAL unnest(p.conkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=p.conrelid AND a.attnum=k.attnum WHERE p.conrelid=%s::regclass AND p.contype='p' ORDER BY k.ord",('public.'+table,))
            key=[r[0] for r in cursor.fetchall()]
            if key!=['analysis_id']:raise ValueError('Unexpected analysis document identity')
            schema['primary_keys'][table]=key
            fields=[('id','id','String',False,'Identifier of this published v2 analysis document.','analysis_id'),
                ('etfInstrumentId','etf_instrument_id','String',True,'ETF discussed by this report, resolved by the stored Korean exchange ticker.','etf_code'),
                ('analysisAt','analysis_at','Timestamp',False,'Analysis cutoff recorded when this report was produced.','analysis_at'),
                ('availableAt','available_at','Timestamp',False,'Publication time of this completed report.','published_at'),
                ('summary','summary','String',True,'Previously generated analysis text. It is a prior interpretation, not a new observed financial fact.','summary'),
                ('previousReportId','previous_report_id','String',True,'Stored identifier of the preceding report of this kind, when present.','previous_analysis_id'),
                ('displayTitle','display_title','String',False,'ETF name, report kind and analysis date for reading this report.','analysis_at'),
                ('evidenceRunIds','evidence_run_ids','String[]',True,'IDs of successful stored tool executions supporting this report. These historical references require separate resolution before their outputs can substantiate a new factual claim.','analysis_id')]
            props={};mappings={}
            for prop,column,dtype,nullable,description,raw in fields:
                props[prop]={'label':prop,'description':description,'dataType':dtype,'nullable':nullable,'sourceDataType':{'String':'text','String[]':'text[]','Timestamp':'timestamp with time zone'}[dtype],
                    'sourceConstraints':None,'mappingStatus':'ready','apiName':prop,'displayName':prop,'status':'experimental'}
                inputs=[{'schema':'public','table':table,'column':raw}]
                if prop=='etfInstrumentId':inputs += [{'schema':'public','table':'instrument','column':c} for c in ('instrument_id','ticker','market_code')]
                mappings[prop]={'kind':'view_column','schema':'ontology_view','table':view,'column':column,'sqlFile':'sql/views/'+view+'.sql','inputs':inputs}
            link=kind+'_ForETF_ETF'
            description=('One published v2 outlook report for an ETF.' if category=='outlook' else 'One published v2 explanation of an ETF price movement.')+' The document preserves an earlier interpretation and its analysis cutoff.'
            doc={'formatVersion':2,'name':kind,'label':kind,'description':description,'group':'Analysis reports','primaryKey':'id',
                'identity':{'columns':key,'encoding':'sourceString'},'properties':props,'sourceMapping':{'connection':'aws_work','schema':'public','baseTable':table,
                'joins':[],'filters':[{'column':'status','operator':'equals','value':'completed'},{'column':'data_source','operator':'equals','value':'database'}],'properties':mappings},
                'sourceConstraints':{},'dataIssues':['Only completed, published database-backed v2 reports are exposed. Unknown-source and failed runs are excluded.',
                    'Historical tool-run IDs are preserved but their outputs are not yet graph-resolvable; treat prior report text as interpretation, not fact evidence.'],
                'apiName':kind,'displayName':kind,'pluralDisplayName':kind+'s','titleProperty':'displayTitle','status':'experimental','visibility':'normal','linkTypes':[link]}
            relationship={'id':link,'source':kind,'definition':{'name':'ForETF','label':'For ETF','description':'The ETF discussed by this published analysis report.',
                'target':'ETF','sourceProperty':'etfInstrumentId','targetProperty':'id','cardinality':'N:1','status':'experimental','sourceMapping':{'kind':'propertyMatch'},
                'mappingStatus':'defined','apiName':'forETF','displayName':'For ETF','pluralDisplayName':'For ETF',
                'inverse':{'apiName':'outlookReports' if category=='outlook' else 'priceExplanations','displayName':'Outlook reports' if category=='outlook' else 'Price explanations',
                    'description':description,'pluralDisplayName':None},'backing':{'type':'foreignKey','configurationStatus':'ready'}}}
            for relative,value in [('object_types/'+kind+'.yaml',doc),('link_types/'+link+'.yaml',relationship)]:
                if (EDGE_ONTOLOGY/'metadata'/relative).exists():raise ValueError('Already promoted '+relative)
                (METADATA/relative).write_text(yaml.safe_dump(value,allow_unicode=True,sort_keys=False),encoding='utf8')
            sql=f'''CREATE OR REPLACE VIEW ontology_view.{view} AS
SELECT a.analysis_id::text AS id,e.id::text AS etf_instrument_id,
       a.analysis_at::timestamptz AS analysis_at,a.published_at::timestamptz AS available_at,
       a.summary::text AS summary,a.previous_analysis_id::text AS previous_report_id,
       concat_ws(' / ',e.name,'{category}',a.analysis_at::text)::text AS display_title,
       ARRAY(SELECT t.tool_run_id::text FROM public.tool_runs t WHERE t.{category}_analysis_id=a.analysis_id AND t.status='completed' ORDER BY t.tool_run_id)::text[] AS evidence_run_ids
FROM public.{table} a
LEFT JOIN ontology_view.etf e ON e.ticker=a.etf_code AND e.market_code='XKRX'
WHERE a.status='completed' AND a.data_source='database' AND a.published_at IS NOT NULL'''
            if category=='movement':sql+=' AND a.withdrawn_at IS NULL'
            (APP/'sql/views'/(view+'.sql')).write_text(sql+';\n',encoding='utf8')
            plan['objects'][kind]={'viewName':'ontology_view.'+view,'grain':description,'issues':[],'referenceColumns':[]}
            plan['relations'][link]={'readiness':'proposal','rowPolicy':'matched_object_pair','grain':relationship['definition']['description'],
                'issues':[],'edgeIdentity':['id'],'physicalMapping':{'kind':'object_fk','source':kind,'edgeIdColumns':['id'],
                'fromColumn':'id','toColumn':'etf_instrument_id','filters':{},'properties':{},'endpointPolicy':'existing_typed_objects_only'}}
    schema.setdefault('extensions',[]).append({'tables':['outlook_analyses','movement_analyses'],'capturedAt':datetime.now(timezone.utc).isoformat()})
    schema_path.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    docs=read_definitions(METADATA/'object_types',EDGE_ONTOLOGY/'metadata')
    plan['definitionHashes']={key:hashlib.sha256(raw.encode('utf8')).hexdigest() for _,doc,_ in docs if doc['sourceMapping'].get('kind')!='curated'
        for key,raw in doc['_definitionSources'].items() if not key.startswith('interface_types/')}
    plan['revision']+=1;plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    assert not read_catalog()['modelChanged']


if __name__=='__main__':prepare()
