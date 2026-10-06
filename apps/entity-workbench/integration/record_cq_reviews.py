"""Record explicit review decisions; this does not infer grades or measure coverage."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('decisions',type=Path);args=parser.parse_args()
    decisions=json.loads(args.decisions.read_text(encoding='utf8'))
    for name,decision in decisions.items():
        root=(args.decisions.parent/'agent-runs').resolve();directory=(root/name).resolve()
        if directory.parent!=root:raise ValueError('Review run must be directly inside agent-runs')
        path=directory/'benchmark.json';report=json.loads(path.read_text(encoding='utf8'))
        if report['status']=='running':raise ValueError('Cannot grade an unfinished run')
        proofs=[]
        for source in (directory/'tools').glob('cq_*.json'):
            record=json.loads(source.read_text(encoding='utf8'))
            if not record['error'] and record['tool'] in decision['proof_tools']:
                proofs.append({'tool':record['tool'],'tool_run_id':record['response']['tool_run_id']})
        report.update(semantic_grade=decision['grade'],review={
            'method':'Primary agent semantic judgment of saved answer and tool evidence; this script only records decisions',
            'reviewed_at':datetime.now(timezone.utc).isoformat(),'findings':decision['findings'],
            'supporting_tool_runs':proofs,'scope':'One actual input, not all canonical variants',
            'answer_sha256':hashlib.sha256(json.dumps(report.get('response'),ensure_ascii=False,sort_keys=True).encode()).hexdigest()})
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'reviews_recorded':len(decisions)}))
