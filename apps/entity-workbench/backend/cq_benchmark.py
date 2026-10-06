"""Read saved benchmark evidence. Never execute queries or treat answered as passed."""
import json
import re
from pathlib import Path
from paths import ROOT,APP
from backend.cq_evaluation import evaluate, contract_for, records

RUNS=ROOT/'output/cq-tools-benchmark-20261005/agent-runs'


def latest_cases(runs):
    """Count each canonical CQ once; pilots and efficiency tests cannot inflate CQ success."""
    latest={}
    for run in runs:
        match=re.fullmatch(r'(CQ(?:0[1-9]|1[0-3]))-(?:suite|cloud)-(\d{8}T\d{6}Z)',run['run_id'])
        if not match:continue
        case,stamp=match.groups()
        if case not in latest or stamp>latest[case][0]:latest[case]=(stamp,run)
    return [{'case':case,'run_id':run['run_id'],'status':run['status'],
        'semantic_grade':run.get('semantic_grade','not_reviewed')} for case,(_,run) in sorted(latest.items())]


def catalog():
    runs=[]
    for path in sorted(RUNS.glob('*/benchmark.json'),reverse=True):
        report=json.loads(path.read_text(encoding='utf8'))
        runs.append({**report,'run_id':path.parent.name,**links(path.parent.name)})
    review=RUNS.parent/'baseline-review.json';efficiency=RUNS.parent/'efficiency/report.json'
    capabilities=APP/'data/cq-tool-capabilities.json'
    cases=json.loads((APP/'data/cq-cases.json').read_text(encoding='utf8'))['cases']
    return {'runs':runs,'cases':[{'id':c['id'],'title':contract_for(c['id'])['title'],'question':c['canonical_question'],'scenario_question':c['question']} for c in cases],
        'latest_cases':latest_cases(runs),'coverage':{'status':'not_measured','target':0.8,
        'definition':'질문 목적에 실제 기여한 객체·관계 사용. 조회 건수나 출처 수로 채점하지 않습니다.'},
        'baseline_review':json.loads(review.read_text(encoding='utf8')) if review.exists() else None,
        'efficiency':json.loads(efficiency.read_text(encoding='utf8')) if efficiency.exists() else None,
        'tool_capabilities':json.loads(capabilities.read_text(encoding='utf8')) if capabilities.exists() else None,
        'implementation_status':'in_progress','planned_cqs':13,
        'notice':'답변 생성과 CQ 통과는 별도입니다. 각 실행에 로컬·클라우드 환경과 의미 평가 결과를 표시합니다. 80% 데이터 커버리지는 아직 검증되지 않았습니다.'}


def run_directory(run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id):raise ValueError('Invalid run identifier')
    path=RUNS/run_id
    if path.resolve().parent!=RUNS.resolve() or not (path/'benchmark.json').is_file():
        raise ValueError('Saved analysis not found')
    return path


def links(run_id):
    return {'analysis_url':'/benchmark/analysis?run_id='+run_id,'benchmark_url':'/benchmark?run_id='+run_id}


def detail(run_id):
    directory=run_directory(run_id);report=json.loads((directory/'benchmark.json').read_text(encoding='utf8'))
    calls=records(directory)
    return {'run':{**report,'run_id':run_id,**links(run_id)},'evaluation':evaluate(directory),
        **links(run_id),'tools':[{'tool_run_id':c['response']['tool_run_id'],'tool':c['tool'],
            'arguments':c['arguments'],'error':c.get('error'),'elapsed_ms':c.get('elapsed_ms'),
            'finished_at':c.get('finished_at')} for c in calls],
        'artifacts':[name for name in ARTIFACTS if (directory/'model'/name).is_file()]}


ARTIFACTS=('response.json','input.json','output_schema.json','tool_schemas.json','system_prompt.txt','AGENTS.md','workspace.json')


def artifact(run_id,name):
    if name not in ARTIFACTS:raise ValueError('Artifact is not public')
    path=run_directory(run_id)/'model'/name
    if not path.is_file() or path.resolve().parent!=(run_directory(run_id)/'model').resolve():raise ValueError('Artifact not found')
    return {'name':name,'text':path.read_text(encoding='utf8')}


def trace(run_id,offset=0,limit=25):
    offset=int(offset);limit=int(limit)
    if offset<0 or not 1<=limit<=50:raise ValueError('Invalid trace page')
    path=run_directory(run_id)/'model/events.jsonl';events=[];next_offset=None
    if path.exists():
        with path.open(encoding='utf8') as stream:
            for index,line in enumerate(stream):
                if index<offset:continue
                if len(events)==limit:next_offset=index;break
                try:events.append(json.loads(line))
                except json.JSONDecodeError:events.append({'message_type':'InvalidRecord','line':index+1})
    return {'events':events,'offset':offset,'next_offset':next_offset,'recorded':path.exists()}


def evidence(run_id,tool_run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id) or not re.fullmatch(r'cq_[a-f0-9]{32}',tool_run_id):
        raise ValueError('Invalid evidence identifier')
    path=run_directory(run_id)/'tools'/(tool_run_id+'.json')
    if not path.is_file():raise ValueError('Evidence not found')
    record=json.loads(path.read_text(encoding='utf8'))
    # Full stored datasets are server evidence; the dashboard shows the exact public response.
    return {key:record[key] for key in ('tool','arguments','response','cutoff','elapsed_ms','queries','error')}
