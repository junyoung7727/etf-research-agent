"""Read saved benchmark evidence. Never execute queries or treat answered as passed."""
import json
import re
from pathlib import Path
from paths import ROOT,APP

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
        runs.append({**report,'run_id':path.parent.name})
    review=RUNS.parent/'baseline-review.json';efficiency=RUNS.parent/'efficiency/report.json'
    capabilities=APP/'data/cq-tool-capabilities.json'
    return {'runs':runs,'latest_cases':latest_cases(runs),'coverage':{'status':'not_measured','target':0.8,
        'definition':'질문 목적에 실제 기여한 객체·관계 사용. 조회 건수나 출처 수로 채점하지 않습니다.'},
        'baseline_review':json.loads(review.read_text(encoding='utf8')) if review.exists() else None,
        'efficiency':json.loads(efficiency.read_text(encoding='utf8')) if efficiency.exists() else None,
        'tool_capabilities':json.loads(capabilities.read_text(encoding='utf8')) if capabilities.exists() else None,
        'implementation_status':'in_progress','planned_cqs':13,
        'notice':'답변 생성과 CQ 통과는 별도입니다. 각 실행에 로컬·클라우드 환경과 의미 평가 결과를 표시합니다. 80% 데이터 커버리지는 아직 검증되지 않았습니다.'}


def evidence(run_id,tool_run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',run_id) or not re.fullmatch(r'cq_[a-f0-9]{32}',tool_run_id):
        raise ValueError('Invalid evidence identifier')
    path=RUNS/run_id/'tools'/(tool_run_id+'.json')
    if not path.is_file():raise ValueError('Evidence not found')
    record=json.loads(path.read_text(encoding='utf8'))
    # Full stored datasets are server evidence; the dashboard shows the exact public response.
    return {key:record[key] for key in ('tool','arguments','response','cutoff','elapsed_ms','queries','error')}
