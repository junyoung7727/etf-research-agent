"""Download retained ECS evidence and close its temporary graph ingress after the task stops."""
import argparse
import json
from pathlib import Path
import boto3


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('launch',type=Path);args=parser.parse_args()
    record=json.loads(args.launch.read_text(encoding='utf8'))
    aws=boto3.Session(profile_name='work',region_name='ap-northeast-2')
    task=aws.client('ecs').describe_tasks(cluster=record['cluster'],tasks=[record['task']])['tasks'][0]
    if task['lastStatus']!='STOPPED':raise ValueError('Task has not completed')
    destination=args.launch.parent/'agent-runs'/record['run_id'];destination.mkdir(parents=True,exist_ok=True)
    s3=aws.client('s3');prefix=record['output_prefix']+'/'
    for page in s3.get_paginator('list_objects_v2').paginate(Bucket=record['bucket'],Prefix=prefix):
        for obj in page.get('Contents',[]):
            suffix=obj['Key'][len(prefix):];target=(destination/suffix).resolve()
            if not target.is_relative_to(destination.resolve()):raise ValueError('Invalid output path')
            target.parent.mkdir(parents=True,exist_ok=True);s3.download_file(record['bucket'],obj['Key'],str(target))
    verification={'task_status':task['lastStatus'],'exit_codes':[c.get('exitCode') for c in task['containers']],
        'image_digests':[c.get('imageDigest') for c in task['containers']],'code_commit':record['code_commit'],
        'bundle_sha256':record['bundle_sha256'],'task':record['task']}
    aws.client('ec2').revoke_security_group_ingress(GroupId=record['ingress_group'],IpPermissions=[record['temporary_ingress']])
    verification['temporary_graph_ingress_removed']=True
    (destination/'cloud-verification.json').write_text(json.dumps(verification,indent=2),encoding='utf8')
    if not (destination/'benchmark.json').exists():raise ValueError('Task did not retain a benchmark result; inspect cloud logs')
    print(json.dumps(verification))
