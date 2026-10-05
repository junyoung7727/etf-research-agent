"""Promote only the three reviewed CQ objects and their direct links, preserving other drafts."""
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from paths import METADATA,EDGE_ONTOLOGY
from backend.file_changes import file_changes
from backend.view_design import read_catalog


if __name__=='__main__':
    before=read_catalog()
    if before['modelChanged']:raise ValueError('Mappings are not reviewed')
    changes={};records=[]
    for kind,target in [('EventMeasurement','SourceEvent'),('ETFOutlookReport','ETF'),('ETFPriceExplanation','ETF')]:
        for key in ['object_types/'+kind+'.yaml','link_types/'+kind+'_For'+('Event' if kind=='EventMeasurement' else 'ETF')+'_'+target+'.yaml']:
            source=METADATA/key;destination=EDGE_ONTOLOGY/'metadata'/key
            if not source.is_file():raise ValueError('Reviewed draft missing: '+key)
            raw=source.read_bytes()
            if destination.exists() and destination.read_bytes()!=raw:raise ValueError('Library has a different definition: '+key)
            changes[destination]=raw;changes[source]=None
            records.append({'definition':key,'sha256':hashlib.sha256(raw).hexdigest()})
    with file_changes(changes):
        after=read_catalog()
        if before!=after:raise ValueError('Promotion changed the effective graph contract')
    out=APP.parents[1]/'output/cq-tools-benchmark-20261005/model-promotion.json'
    out.write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'definitions':records,
        'effective_graph_unchanged':True,'other_drafts_preserved':True},indent=2),encoding='utf8')
    print(json.dumps({'promoted':len(records),'effective_graph_unchanged':True}))
