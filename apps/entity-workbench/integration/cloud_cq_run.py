"""Run the actual CQ provider in an isolated ECS task and retain its exact evidence in S3."""
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
from time import perf_counter

import boto3
from neo4j import GraphDatabase,Query

ROOT=Path(__file__).resolve().parent
APP=ROOT/'apps/entity-workbench'
sys.path.insert(0,str(APP));sys.path.insert(0,str(APP/'integration'))
from backend.cq_tools import CQTools
from run_cq_agent import PROMPT,OUTPUT
from edge_analysis_v2.agent.runner import run_model


async def main():
    aws=boto3.Session(region_name='ap-northeast-2')
    catalog=json.loads((ROOT/'graph-catalog.json').read_text(encoding='utf8'))
    contract=json.loads((APP/'data/cq-cases.json').read_text(encoding='utf8'))
    case=next(c for c in contract['cases'] if c['id']==os.environ['CQ_CASE'])
    directory=ROOT/'result';directory.mkdir()
    report={'case':case['id']+'-cloud','kind':'real_v2_agent','execution_host':'AWS ECS Fargate',
        'question':case['question'],'cutoff':contract['cutoff'],'status':'running','semantic_grade':'not_reviewed',
        'code_commit':os.environ['CQ_COMMIT'],'bundle_sha256':os.environ['CQ_BUNDLE_SHA'],
        'coverage':'not_measured','model':'deepseek-flash'}
    credentials=json.loads(aws.client('ssm').get_parameter(Name=os.environ['GRAPH_PARAMETER'],WithDecryption=True)['Parameter']['Value'])
    secret=json.loads(aws.client('secretsmanager').get_secret_value(SecretId=os.environ['DEEPSEEK_SECRET_ARN'])['SecretString'])
    key=secret['DEEPSEEK_API_KEY'];provider=None;started=perf_counter()
    try:
        with GraphDatabase.driver('bolt://'+os.environ['GRAPH_HOST']+':7687',auth=(credentials['username'],credentials['password']),connection_timeout=15) as driver:
            with driver.session(default_access_mode='READ') as session:
                provider=CQTools(lambda q,p:[r.data() for r in session.run(Query(q,timeout=25),p)],catalog,directory/'tools',contract['cutoff'])
                response=await run_model(initial={'question':case['question'],'analysis_cutoff':contract['cutoff']},
                    prompt=PROMPT,schemas=provider.schemas,call=provider.call,output_schema=OUTPUT,
                    artifacts=directory/'model',key=key,model=report['model'],timeout_seconds=600)
                report.update(status='answered',response=response)
                successful={r['response']['tool_run_id'] for r in provider.store.calls if not r['error']}
                cited={i for c in response['claims'] for i in c['tool_run_ids']}
                report['citation_ids_valid']=bool(cited) and cited<=successful
    except Exception as exc:
        report.update(status='error',error=str(exc).replace(key,'[redacted]'))
    finally:
        report['elapsed_ms']=round((perf_counter()-started)*1000,2)
        if provider:
            report.update(tool_calls=len(provider.store.calls),graph_queries=len(provider.graph.queries),
                tools_used=[c['tool'] for c in provider.store.calls],tool_errors=sum(bool(c['error']) for c in provider.store.calls))
        (directory/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        s3=aws.client('s3')
        for path in directory.rglob('*'):
            if path.is_file():s3.upload_file(str(path),os.environ['CQ_BUCKET'],os.environ['CQ_OUTPUT_PREFIX']+'/'+path.relative_to(directory).as_posix())
        print(json.dumps({k:report[k] for k in ('case','status','execution_host','code_commit','elapsed_ms')},ensure_ascii=False),flush=True)


if __name__=='__main__':asyncio.run(main())
