"""Deploy the measurement view and verify source/graph identity, precision and traversal."""
import json
import shutil
import sys
from pathlib import Path
from decimal import Decimal
from psycopg2 import sql

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
sys.path.insert(0,str(APP/'integration'))
from integration.pilot_session import database, OUT
from pilot_graph import graph_session
from backend.view_design import read_catalog


def apply():
    report={}
    destination=APP.parents[1]/'output/cq-tools-benchmark-20261005'
    destination.mkdir(parents=True,exist_ok=True)
    active=OUT/'active-schema-no-credentials.json'
    backup=destination/'schema-before-measurements.json'
    if active.exists() and not backup.exists():shutil.copy2(active,backup)
    with database(writable=True) as db,db.cursor() as c:
        for table in ('actor_participation','document_event_evidence'):
            c.execute('SELECT count(*) FROM ontology_view.'+table)
            before=c.fetchone()[0]
            c.execute((APP/'sql/views'/(table+'.sql')).read_text(encoding='utf8'))
            c.execute('SELECT count(*) FROM ontology_view.'+table)
            assert c.fetchone()[0]==before
        c.execute((APP/'sql/views/event_measurement.sql').read_text(encoding='utf8'))
        c.execute("SELECT DISTINCT grantee FROM information_schema.role_table_grants WHERE table_schema='ontology_view' AND table_name='source_event' AND privilege_type='SELECT'")
        for (role,) in c.fetchall():
            c.execute(sql.SQL('GRANT SELECT ON ontology_view.event_measurement TO {}').format(sql.Identifier(role)))
        c.execute('SELECT count(*),count(DISTINCT id),count(*) FILTER(WHERE value IS NULL) FROM ontology_view.event_measurement')
        report['view_counts']=c.fetchone()
        c.execute('SELECT count(*),count(DISTINCT (source_event_id,measure_ord)),count(*) FILTER(WHERE value IS NULL) FROM public.event_measure')
        report['source_counts']=c.fetchone()
        assert report['view_counts']==report['source_counts']
        c.execute('SELECT id,source_event_id,metric_code,value,unit,period_basis,reported_text FROM ontology_view.event_measurement ORDER BY id LIMIT 100')
        expected={r[0]:r[1:] for r in c.fetchall()}
        db.commit()
    catalog=read_catalog()
    with graph_session([o['id'] for o in catalog['objects']]) as (session,meta):
        count=session.run('MATCH (m:EventMeasurement) RETURN count(m) AS n').single()['n']
        assert count==report['source_counts'][0]
        graph={}
        for row in session.run('MATCH (m:EventMeasurement)-[:EventMeasurement_ForEvent_SourceEvent]->(e:SourceEvent) WHERE m.id IN $ids RETURN m.id AS id,e.id AS event,m.metricCode AS code,m.value AS value,m.unit AS unit,m.periodBasis AS basis,m.reportedText AS text',{'ids':list(expected)}):
            graph[row['id']]=(row['event'],row['code'],Decimal(row['value']) if row['value'] is not None else None,row['unit'],row['basis'],row['text'])
        assert graph==expected
        reverse=session.run('MATCH (e:SourceEvent)<-[:EventMeasurement_ForEvent_SourceEvent]-(m:EventMeasurement) RETURN count(m) AS n').single()['n']
        assert reverse==count
        # Traverse the actual evidence and participant properties; do not infer them from IDs.
        for relation,prop in [('Company_ParticipatesIn_SourceEvent','argumentGroup'),
                              ('NewsArticle_DescribesEvent_SourceEvent','assertionId')]:
            session.run('MATCH ()-[r:'+relation+']->() RETURN r.'+prop+' AS value LIMIT 1').consume()
        report.update(graph_count=count,reverse_edges=reverse,exact_sample_count=len(graph),passed=True,schema=meta)
    (destination/'measurement-graph-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,default=str))


if __name__=='__main__':apply()
