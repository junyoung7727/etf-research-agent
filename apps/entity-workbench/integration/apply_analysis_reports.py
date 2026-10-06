"""Apply published-report graph views and compare their actual IDs and evidence references."""
import json
import sys
from pathlib import Path
from psycopg2 import sql

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP));sys.path.insert(0,str(APP/'integration'))
from integration.pilot_session import database
from pilot_graph import graph_session
from backend.view_design import read_catalog


def apply():
    mapping={'ETFOutlookReport':'etf_outlook_report','ETFPriceExplanation':'etf_price_explanation'}
    expected={}
    with database(writable=True) as db,db.cursor() as c:
        c.execute("SELECT DISTINCT grantee FROM information_schema.role_table_grants WHERE table_schema='ontology_view' AND table_name='source_event' AND privilege_type='SELECT'")
        roles=[r[0] for r in c.fetchall()]
        for kind,view in mapping.items():
            c.execute((APP/'sql/views'/(view+'.sql')).read_text(encoding='utf8'))
            for role in roles:c.execute(sql.SQL('GRANT SELECT ON ontology_view.{} TO {}').format(sql.Identifier(view),sql.Identifier(role)))
            c.execute('SELECT id,etf_instrument_id,evidence_run_ids FROM ontology_view.'+view+' ORDER BY id')
            rows=c.fetchall();assert len(rows)==len({r[0] for r in rows})
            expected[kind]={r[0]:(r[1],r[2]) for r in rows}
        db.commit()
    report={}
    with graph_session([o['id'] for o in read_catalog()['objects']]) as (session,_):
        for kind in mapping:
            rows=session.run('MATCH (r:'+kind+') RETURN r.id AS id,r.etfInstrumentId AS etf,r.evidenceRunIds AS evidence')
            actual={r['id']:(r['etf'],r['evidence']) for r in rows}
            assert actual==expected[kind],kind
            count=session.run('MATCH (r:'+kind+')-[:'+kind+'_ForETF_ETF]->(e:ETF) RETURN count(r) AS n').single()['n']
            assert count==sum(bool(v[0]) for v in expected[kind].values())
            report[kind]={'rows':len(actual),'linked_to_etf':count,'exact_ids_and_evidence':True}
    target=APP.parents[1]/'output/cq-tools-benchmark-20261005/analysis-report-graph.json'
    target.write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))


if __name__=='__main__':apply()
