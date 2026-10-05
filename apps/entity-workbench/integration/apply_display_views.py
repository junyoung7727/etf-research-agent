"""Apply additive display columns and audit identities, values and name resolution."""
import json,sys
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from integration.pilot_session import database
from backend.view_design import read_catalog

OUT=APP.parents[1]/'output/ontology-readable-views-20261005'


def apply(names):
    contract=json.loads((APP/'data/view-display-contracts.json').read_text(encoding='utf-8'))['objects']
    catalog={o['id']:o for o in read_catalog()['objects']}
    if not set(names)<=contract.keys():raise ValueError('Select reviewed view names')
    report={};OUT.mkdir(parents=True,exist_ok=True)
    with database(writable=True) as db,db.cursor() as c:
        for kind in names:
            obj=catalog[kind];view=obj['viewName'];table=view.split('.')[1]
            c.execute('SELECT pg_get_viewdef(%s::regclass,true)',(view,));original=c.fetchone()[0]
            backup=OUT/(table+'-before.sql')
            if not backup.exists():backup.write_text('CREATE OR REPLACE VIEW '+view+' AS\n'+original,encoding='utf-8')
            c.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position',('ontology_view',table))
            old_cols=[r[0] for r in c.fetchall()]
            added={m['column'] for m in contract[kind]['mappings'].values()}
            original_cols=[n for n in old_cols if n not in added]
            if kind=='DailyBar':
                c.execute('SELECT instrument_id FROM public.price_daily GROUP BY instrument_id ORDER BY instrument_id LIMIT 3')
                partitions=[r[0] for r in c.fetchall()]
                where=' WHERE instrument_id=ANY(%s)';params=(partitions,)
            else:where='';params=()
            c.execute('SELECT count(*),count(DISTINCT id),count(*) FILTER(WHERE id IS NULL) FROM '+view+where,params)
            before=c.fetchone()
            columns=','.join(original_cols)
            c.execute('SELECT '+columns+' FROM '+view+where+' ORDER BY id LIMIT 20',params);values_before=c.fetchall()
            c.execute((APP/'sql/views'/f'{table}.sql').read_text(encoding='utf-8'))
            c.execute('SELECT count(*),count(DISTINCT id),count(*) FILTER(WHERE id IS NULL) FROM '+view+where,params)
            after=c.fetchone();assert before==after and after[0]==after[1] and after[2]==0,(kind,before,after)
            c.execute('SELECT '+columns+' FROM '+view+where+' ORDER BY id LIMIT 20',params)
            assert values_before==c.fetchall(),kind+' changed pre-existing values'
            title=obj['titleProperty'];title_col=next(col['column'] for col in obj['columns'] if col.get('property')==title)
            c.execute('SELECT count(*) FILTER(WHERE '+title_col+" IS NULL OR btrim("+title_col+")='') FROM "+view+where,params)
            empty=c.fetchone()[0]
            if title=='displayTitle':assert empty==0,kind+' missing display titles'
            c.execute('SELECT id,'+title_col+' FROM '+view+where+' ORDER BY id LIMIT 3',params);examples=c.fetchall()
            report[kind]={'before':before,'after':after,'originalColumnsCompared':len(original_cols),'sampleValuesUnchanged':True,
                          'emptyTitles':empty,'examples':examples,'scope':'3 security partitions' if kind=='DailyBar' else 'all rows'}
            print(kind,after[0],'rows; identities and original samples unchanged',flush=True)
        db.commit()
    path=OUT/'view-verification.json'
    previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    previous.update(report);path.write_text(json.dumps(previous,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    names=sys.argv[1:] or list(json.loads((APP/'data/view-display-contracts.json').read_text(encoding='utf-8'))['objects'])
    apply(names)
