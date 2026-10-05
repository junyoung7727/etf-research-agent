"""SSM tunnels and private pilot credentials; never print credentials."""
from contextlib import contextmanager
import json
import socket
import subprocess
import time
from pathlib import Path
import boto3
import psycopg2

OUT=Path(__file__).resolve().parents[3]/'output/ontology-views-puppygraph-20261005'

@contextmanager
def database(*, writable=False):
    aws,_,credential=state()
    db=aws.client('rds').describe_db_instances(DBInstanceIdentifier='edge-dev')['DBInstances'][0]
    if writable:
        secret=json.loads(aws.client('secretsmanager').get_secret_value(SecretId=db['MasterUserSecret']['SecretArn'])['SecretString'])
    else:secret={'username':credential['db_username'],'password':credential['db_password']}
    with tunnel(aws,db['Endpoint']['Address'],5432) as port:
        conn=psycopg2.connect(host='127.0.0.1',port=port,dbname='edge',user=secret['username'],password=secret['password'],sslmode='require',options='-c statement_timeout=30000 -c lock_timeout=5000')
        secret.clear()
        conn.set_session(readonly=not writable,isolation_level='REPEATABLE READ')
        try:yield conn
        finally:conn.close()

def state():
    r=json.loads((OUT/'puppy-task.json').read_text())
    s=boto3.Session(profile_name='work',region_name='ap-northeast-2')
    task=s.client('ecs').describe_tasks(cluster=r['cluster'],tasks=[r['task']])['tasks'][0]
    if task['lastStatus']!='RUNNING':raise RuntimeError('Pilot status: '+task['lastStatus']+' '+task.get('stoppedReason',''))
    r['ip']=next(d['value'] for a in task['attachments'] for d in a['details'] if d['name']=='privateIPv4Address')
    r['status']='RUNNING'
    r['imageDigest']=task['containers'][0].get('imageDigest')
    (OUT/'puppy-task.json').write_text(json.dumps(r,indent=2),encoding='utf8')
    credentials=json.loads(s.client('ssm').get_parameter(Name=r['credentialParameter'],WithDecryption=True)['Parameter']['Value'])
    return s,r,credentials

@contextmanager
def tunnel(aws, host, port):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));local=probe.getsockname()[1]
    ssm=aws.client('ssm')
    params={'Target':'i-0ba627536f36993d5','DocumentName':'AWS-StartPortForwardingSessionToRemoteHost','Parameters':{'host':[host],'portNumber':[str(port)],'localPortNumber':[str(local)]}}
    started=ssm.start_session(**params)
    process=None
    try:
        process=subprocess.Popen(['session-manager-plugin',json.dumps(started),'ap-northeast-2','StartSession','work',json.dumps(params),ssm.meta.endpoint_url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(60):
            if process.poll() is not None:raise RuntimeError('Tunnel process exited')
            try:
                with socket.create_connection(('127.0.0.1',local),.2):break
            except OSError:time.sleep(.25)
        else:raise RuntimeError('Tunnel listener unavailable')
        yield local
    finally:
        ssm.terminate_session(SessionId=started['SessionId'])
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
