"""Bump an agent release after edits, or reject an unversioned execution/change."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.agent_version import ROOT,check,bump


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['check','bump'])
    parser.add_argument('--base');parser.add_argument('--summary',default='')
    args=parser.parse_args()
    try:
        result=bump(ROOT,args.summary) if args.action=='bump' else check(ROOT,args.base)
        print(json.dumps(result,ensure_ascii=False))
    except (ValueError,FileNotFoundError) as error:parser.exit(1,str(error)+'\n')
