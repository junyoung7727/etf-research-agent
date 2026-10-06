"""Read-only source audit for data that CQ agents must discover through the graph."""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from integration.pilot_session import database


def audit():
    report = {}
    with database() as db, db.cursor() as c:
        queries = {
            'measure_columns': ("SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND (table_name LIKE '%%measure%%' OR table_name LIKE '%%feature%%') ORDER BY 1,ordinal_position", ()),
            'measure_constraints': ("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='public.event_measure'::regclass ORDER BY 1", ()),
            'measure_codes': ("SELECT role_code,unit,basis,value_source,parse_flag,count(*) FROM public.event_measure GROUP BY 1,2,3,4,5 ORDER BY 6 DESC", ()),
            'measure_examples': ("SELECT row_to_json(m) FROM public.event_measure m ORDER BY source_event_id,measure_ord LIMIT 3", ()),
            'tables': ("SELECT table_schema,table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') AND (table_name LIKE '%%assertion%%' OR table_name LIKE '%%analyses%%' OR table_name LIKE '%%expectation%%' OR table_name IN ('tool_runs','event_evidence')) ORDER BY 1,2", ()),
            'columns': ("SELECT table_schema,table_name,column_name,data_type FROM information_schema.columns WHERE table_name IN ('document_assertion','assertion_metric','assertion_argument','event_evidence','outlook_analyses','movement_analyses','tool_runs') ORDER BY 1,2,ordinal_position", ()),
            'constraints': ("SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid IN ('public.document_assertion'::regclass,'public.assertion_metric'::regclass,'public.assertion_argument'::regclass,'public.event_evidence'::regclass) ORDER BY 1,2", ()),
            'metrics': ("SELECT metric_code,unit_code,period_basis,integrity_status,count(*) FROM public.assertion_metric GROUP BY 1,2,3,4 ORDER BY 5 DESC", ()),
            'modalities': ("SELECT modality_code,event_type_code,count(*) FROM public.document_assertion GROUP BY 1,2 ORDER BY 3 DESC", ()),
            'evidence': ("SELECT evidence_type,count(*),count(DISTINCT assertion_id),count(DISTINCT source_event_id) FROM public.event_evidence GROUP BY 1", ()),
            'identity': ("SELECT 'assertion',count(*),count(DISTINCT assertion_id) FROM public.document_assertion UNION ALL SELECT 'metric',count(*),count(DISTINCT assertion_metric_id) FROM public.assertion_metric UNION ALL SELECT 'argument',count(*),count(DISTINCT assertion_argument_id) FROM public.assertion_argument", ()),
            'orphan_metrics': ("SELECT count(*) FROM public.assertion_metric m LEFT JOIN public.document_assertion a USING(assertion_id) WHERE a.assertion_id IS NULL", ()),
            'actor_types': ("SELECT e.entity_type,a.actor_type,count(*) FROM public.assertion_argument x LEFT JOIN public.entity e ON e.entity_id=x.entity_id LEFT JOIN public.actor a ON a.actor_id=x.entity_id GROUP BY 1,2 ORDER BY 3 DESC", ()),
        }
        for key, (sql, params) in queries.items():
            c.execute(sql, params)
            report[key] = [list(row) for row in c.fetchall()]
            print(key, json.dumps(report[key], ensure_ascii=False, default=str), flush=True)
    destination = APP.parents[1] / 'output/cq-tools-benchmark-20261005'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'graph-gap-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    return report


if __name__ == '__main__':
    audit()
