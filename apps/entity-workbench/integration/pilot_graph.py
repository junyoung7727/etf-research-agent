import base64
import json
import sys
import urllib.request
import urllib.error
from contextlib import contextmanager
from neo4j import GraphDatabase
from pilot_session import state,tunnel,OUT

sys.path.insert(0,str(OUT.parents[1]/'apps/entity-workbench'))
from backend.view_design import read_catalog
from backend.puppygraph_schema import build_schema


@contextmanager
def graph_session(object_names, schema_override=None):
    aws,r,credential=state()
    graph,report=build_schema(read_catalog(),object_names) if schema_override is None else (schema_override, {})
    (OUT/'active-schema-no-credentials.json').write_text(json.dumps(graph,indent=2),encoding='utf8')
    db=aws.client('rds').describe_db_instances(DBInstanceIdentifier='edge-dev')['DBInstances'][0]
    graph['catalog']=[{'name':'ontology','type':'postgresql','jdbc':{'username':credential['db_username'],'password':credential['db_password'],'jdbcUri':'jdbc:postgresql://'+db['Endpoint']['Address']+':5432/edge?sslmode=require'}}]
    with tunnel(aws,r['ip'],8081) as port:
        request=urllib.request.Request(f'http://127.0.0.1:{port}/schema?postUploadBehavior=none',data=json.dumps(graph).encode(),headers={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode((credential['username']+':'+credential['password']).encode()).decode()})
        try:
            with urllib.request.urlopen(request,timeout=60) as response:
                payload=json.loads(response.read());assert response.status==200
                if isinstance(payload,dict) and payload.get('ok') is False:
                    raise RuntimeError('Schema upload returned ok=false')
        except urllib.error.HTTPError as e:
            text=e.read().decode()
            for key in ['password','db_password']:text=text.replace(credential[key],'[redacted]')
            raise RuntimeError(text[:2000]) from None
    with tunnel(aws,r['ip'],7687) as port:
        with GraphDatabase.driver(f'bolt://127.0.0.1:{port}',auth=(credential['username'],credential['password']),connection_timeout=15) as driver:
            with driver.session() as session:
                yield session,report
