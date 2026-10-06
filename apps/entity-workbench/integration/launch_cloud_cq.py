"""Deploy a content-addressed code bundle to a read-only CQ task; never update customer services."""
import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import zipfile
from datetime import datetime,timezone
from pathlib import Path

import boto3

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from backend.view_design import read_catalog
from integration.pilot_session import state
from backend.agent_version import check


def launch(case,checkout):
    checkout=Path(checkout).resolve();source=checkout/'apps/entity-workbench'
    if checkout!=APP.parents[1].resolve():raise ValueError('Run the launcher from the selected checkout')
    check(checkout)
    if subprocess.check_output(['git','status','--porcelain'],cwd=checkout,text=True).strip():raise ValueError('Commit the cloud bundle sources first')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as archive:
        for folder in ('backend','ontology/oms'):
            for path in (source/folder).glob('*.py'):archive.write(path,'apps/entity-workbench/'+path.relative_to(source).as_posix())
        for path in ['paths.py','integration/run_cq_agent.py','data/cq-cases.json','data/cq-coverage-contract.json',
                     'data/cq-evaluation-contract.json','data/agent-version.json']:
            archive.write(source/path,'apps/entity-workbench/'+path)
        archive.write(source/'integration/cloud_cq_run.py','cloud_cq_run.py')
        archive.writestr('graph-catalog.json',json.dumps(read_catalog(),ensure_ascii=False))
        # neo4j is a pure Python client. Bundle installed dependencies without adding a mutable pip install to deployment.
        for package in ('neo4j','pytz'):
            root=Path(importlib.util.find_spec(package).origin).parent
            for path in root.rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:archive.write(path,package+'/'+path.relative_to(root).as_posix())
    raw=data.getvalue();digest=hashlib.sha256(raw).hexdigest()
    aws,runtime,_=state();ecs=aws.client('ecs');iam=aws.client('iam');ec2=aws.client('ec2');s3=aws.client('s3')
    base=ecs.describe_task_definition(taskDefinition='edge-dev-analysis-v2')['taskDefinition']
    original=base['containerDefinitions'][0];env={e['name']:e['value'] for e in original['environment']}
    bucket=env['OBSERVATION_BUCKET'];prefix='analysis-v2/runs/cq-graph-benchmark'
    object_key=prefix+'/bundles/'+digest+'.zip'
    s3.put_object(Bucket=bucket,Key=object_key,Body=raw,ServerSideEncryption='AES256')
    role_name='edge-dev-cq-graph-benchmark-task'
    try:role=iam.get_role(RoleName=role_name)['Role']
    except iam.exceptions.NoSuchEntityException:
        role=iam.create_role(RoleName=role_name,AssumeRolePolicyDocument=json.dumps({'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'ecs-tasks.amazonaws.com'},'Action':'sts:AssumeRole'}]}))['Role']
    account=role['Arn'].split(':')[4]
    policy={'Version':'2012-10-17','Statement':[
        {'Effect':'Allow','Action':'secretsmanager:GetSecretValue','Resource':env['DEEPSEEK_SECRET_ARN']},
        {'Effect':'Allow','Action':'ssm:GetParameter','Resource':'arn:aws:ssm:ap-northeast-2:'+account+':parameter'+runtime['credentialParameter']},
        {'Effect':'Allow','Action':['s3:GetObject','s3:PutObject'],'Resource':'arn:aws:s3:::'+bucket+'/'+prefix+'/*'}]}
    iam.put_role_policy(RoleName=role_name,PolicyName='cq-graph-benchmark-only',PolicyDocument=json.dumps(policy))
    service=ecs.describe_services(cluster='edge-dev-worker',services=['edge-dev-data-pipeline-news-worker'])['services'][0]
    network=service['networkConfiguration'];group=network['awsvpcConfiguration']['securityGroups'][0]
    permission={'IpProtocol':'tcp','FromPort':7687,'ToPort':7687,'UserIdGroupPairs':[{'GroupId':group,'Description':'CQ read-only graph benchmark'}]}
    try:ec2.authorize_security_group_ingress(GroupId='sg-055632812d205b566',IpPermissions=[permission])
    except ec2.exceptions.ClientError as exc:
        if exc.response['Error']['Code']!='InvalidPermission.Duplicate':raise
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');run_id=case+'-cloud-'+stamp
    bootstrap="import boto3,hashlib,io,os,sys,zipfile; raw=boto3.client('s3').get_object(Bucket=os.environ['CQ_BUCKET'],Key=os.environ['CQ_BUNDLE_KEY'])['Body'].read(); assert hashlib.sha256(raw).hexdigest()==os.environ['CQ_BUNDLE_SHA']; root='/tmp/cq-graph'; zipfile.ZipFile(io.BytesIO(raw)).extractall(root); sys.path.insert(0,root); os.chdir(root); import cloud_cq_run; import asyncio; asyncio.run(cloud_cq_run.main())"
    allowed=set(ecs.meta.service_model.operation_model('RegisterTaskDefinition').input_shape.members)
    task={k:v for k,v in base.items() if k in allowed};task.update(family='edge-dev-cq-graph-benchmark',taskRoleArn=role['Arn'])
    container=task['containerDefinitions'][0]
    container.update(entryPoint=['python','-c'],command=[bootstrap])
    variables={**env,'CQ_CASE':case,'CQ_COMMIT':sha,'CQ_BUCKET':bucket,'CQ_BUNDLE_KEY':object_key,
        'CQ_BUNDLE_SHA':digest,'CQ_OUTPUT_PREFIX':prefix+'/results/'+run_id,'GRAPH_HOST':runtime['ip'],
        'GRAPH_PARAMETER':runtime['credentialParameter']}
    container['environment']=[{'name':k,'value':v} for k,v in variables.items()]
    definition=ecs.register_task_definition(**task)['taskDefinition']['taskDefinitionArn']
    result=ecs.run_task(cluster='edge-dev-worker',taskDefinition=definition,launchType='FARGATE',networkConfiguration=network,startedBy='cq-graph-benchmark',count=1)
    if result.get('failures'):raise RuntimeError(result['failures'])
    launched=result['tasks'][0];record={'run_id':run_id,'task':launched['taskArn'],'cluster':'edge-dev-worker',
        'code_commit':sha,'bundle_sha256':digest,'bundle_key':object_key,'bucket':bucket,
        'output_prefix':variables['CQ_OUTPUT_PREFIX'],'task_definition':definition,'base_image':container['image'],
        'log_group':container['logConfiguration']['options']['awslogs-group'],
        'log_stream':container['logConfiguration']['options']['awslogs-stream-prefix']+'/'+container['name']+'/'+launched['taskArn'].split('/')[-1],
        'ingress_group':'sg-055632812d205b566','temporary_ingress':permission,'task_role':role_name}
    out=APP.parents[1]/'output/cq-tools-benchmark-20261005'/('cloud-launch-'+run_id+'.json')
    out.write_text(json.dumps(record,indent=2),encoding='utf8');print(json.dumps(record))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',default='CQ07');parser.add_argument('--checkout',required=True)
    args=parser.parse_args();launch(args.case,args.checkout)
