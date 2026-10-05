import json
from pilot_graph import graph_session,read_catalog
from pilot_session import database,OUT
schema={'node':[{'label':'DeploymentProbe','id':[{'name':'id','type':'STRING'}],
    'attribute':[{'name':'id','type':'STRING'},{'name':'amount','type':'STRING'}],
    'dataSourceGroup':{'externalDataSource':{'enabled':True,'catalog':'ontology','schema':'ontology_view','table':'deployment_probe',
    'mappedField':[{'sourceFieldName':p,'targetFieldName':p} for p in ['id','amount']]}}}],'edge':[]}
report={}
try:
    with database(writable=True) as conn,conn,conn.cursor() as c:
        c.execute("CREATE VIEW ontology_view.deployment_probe AS SELECT 'probe'::text AS id,12345678901234567890.12345678::numeric::text AS amount")
        c.execute('GRANT SELECT ON ontology_view.deployment_probe TO agent_ro')
    with graph_session([],schema) as (session,_):
        before=session.run('MATCH (n:DeploymentProbe) RETURN n.amount AS value').single()['value']
        assert before=='12345678901234567890.12345678'
        with database(writable=True) as conn,conn,conn.cursor() as c:
            c.execute("CREATE OR REPLACE VIEW ontology_view.deployment_probe AS SELECT 'probe'::text AS id,12345678901234567890.12345679::numeric::text AS amount")
        after=session.run('MATCH (n:DeploymentProbe) RETURN n.amount AS value').single()['value']
        assert after=='12345678901234567890.12345679'
        report.update(exactDecimalText=True,sourceChangeVisibleWithoutGraphReload=True)
finally:
    with graph_session([o['id'] for o in read_catalog()['objects']]) as (session,meta):
        assert session.run('MATCH (n:Company) RETURN count(n) AS n').single()['n']==2766
        report['fullSchemaRestored']=True;report['nodes']=len(meta['objectTypes'])
    with database(writable=True) as conn,conn,conn.cursor() as c:c.execute('DROP VIEW IF EXISTS ontology_view.deployment_probe')
(OUT/'redeployment.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
