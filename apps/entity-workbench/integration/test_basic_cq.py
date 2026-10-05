import json,time,statistics
from decimal import Decimal
from datetime import date,datetime,timezone
from pilot_graph import graph_session,read_catalog
from pilot_session import OUT,database

catalog=read_catalog();report={'cutoff':'2026-10-05T00:00:00Z','basicChecks':{},'performance':[],'fullCqPassed':False}
def norm(v):
    if hasattr(v,'to_native'):v=v.to_native()
    if isinstance(v,datetime):return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
    return v
def save():(OUT/'basic-cq.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf8')
with graph_session([o['id'] for o in catalog['objects']]) as (session,meta),database() as conn,conn.cursor() as c:
    c.execute("SELECT instrument_id FROM instrument WHERE ticker='449450' AND instrument_type='ETF'");etf=c.fetchone()[0]
    c.execute('SELECT max(trade_date) FROM etf_holding_snapshot WHERE etf_instrument_id=%s AND available_at<=%s',(etf,report['cutoff']));day=c.fetchone()[0];assert day
    c.execute('SELECT h.constituent_instrument_id,en.display_name,h.weight_ratio,e.issuer_actor_id FROM etf_holding_snapshot h JOIN instrument i ON i.instrument_id=h.constituent_instrument_id JOIN entity en ON en.entity_id=i.instrument_id JOIN equity_profile e ON e.instrument_id=i.instrument_id WHERE h.etf_instrument_id=%s AND h.trade_date=%s AND h.available_at<=%s ORDER BY 1',(etf,day,report['cutoff']))
    expected=c.fetchall()
    q='MATCH (f:ETF)<-[:ETFHolding_ForETF_ETF]-(h:ETFHolding)-[:ETFHolding_HoldsSecurity_Equity]->(s:Equity)<-[:Company_Issues_Equity]-(c:Company) WHERE f.id=$etf AND h.tradeDate=date($date) AND h.availableAt<=datetime($cutoff) RETURN s.id AS id,s.name AS name,h.weightRatio AS weight,c.id AS company ORDER BY id'
    actual=[tuple(r.values()) for r in session.run(q,etf=etf,date=str(day),cutoff=report['cutoff'])]
    assert actual==expected,(actual,expected)
    report['basicChecks']['composition']={'passed':True,'etf':etf,'date':str(day),'rows':actual,'queries':1};save()
    ids=[r[0] for r in expected];companies=[r[3] for r in expected]
    for label,selection in [('single',ids[:1]),('list',ids[:3]),('whole_etf',ids)]:
        sql='SELECT instrument_id,trade_date,close_price,adjusted_close_price,volume,price_basis FROM price_daily WHERE instrument_id=ANY(%s) AND trade_date BETWEEN %s AND %s AND available_at<=%s ORDER BY 1,2'
        cypher='MATCH (s:Equity)<-[:DailyBar_ForSecurity_Equity]-(p:DailyBar) WHERE s.id IN $ids AND p.instrumentId IN $ids AND p.tradeDate>=date($start) AND p.tradeDate<=date($end) AND p.availableAt<=datetime($cutoff) RETURN s.id AS id,p.tradeDate AS day,p.closePrice AS close,p.adjustedClosePrice AS adjusted,p.volume AS volume,p.priceBasis AS basis ORDER BY id,day'
        timings=[]
        for iteration in range(3):
            start=time.perf_counter();c.execute(sql,(selection,'2026-09-01',day,report['cutoff']));raw=c.fetchall();sqlms=(time.perf_counter()-start)*1000
            start=time.perf_counter();rows=list(session.run(cypher,ids=selection,start='2026-09-01',end=str(day),cutoff=report['cutoff']));graphms=(time.perf_counter()-start)*1000
            actual=[(r['id'],norm(r['day']),Decimal(r['close']) if r['close'] is not None else None,Decimal(r['adjusted']) if r['adjusted'] is not None else None,r['volume'],r['basis']) for r in rows]
            assert actual==raw,label
            timings.append({'sqlMs':sqlms,'graphMs':graphms})
        report['performance'].append({'scope':label,'securities':len(selection),'rows':len(raw),'exact':True,'queryCountPerRequest':1,'iterations':timings,'sqlMedianMs':statistics.median(t['sqlMs'] for t in timings),'graphMedianMs':statistics.median(t['graphMs'] for t in timings),'outputBytes':len(json.dumps(actual,default=str).encode())});save();print(label,report['performance'][-1],flush=True)
    report['basicChecks']['priceContext']={'passed':True,'scope':'whole_etf','rows':len(raw),'causeClaim':False}
    sql="SELECT a.entity_id,a.event_argument_id::text,e.source_event_id,a.role_code,e.event_type_code,e.event_date,e.lifecycle_stage FROM event_argument a JOIN source_event e USING(source_event_id) WHERE a.entity_id=ANY(%s) AND a.role_code='SUPPLIER' AND e.event_type_code='COMPANY.CONTRACT.SIGNING' AND e.available_at<=%s ORDER BY 1,2"
    c.execute(sql,(companies,report['cutoff']));expected=c.fetchall()
    q="MATCH (c:Company)-[p:Company_ParticipatesIn_SourceEvent]->(e:SourceEvent) WHERE c.id IN $companies AND p.roleCode='SUPPLIER' AND e.eventType='COMPANY.CONTRACT.SIGNING' AND e.availableAt<=datetime($cutoff) RETURN c.id AS actor,p.key_0 AS participation,e.id AS event,p.roleCode AS role,e.eventType AS type,e.eventDate AS day,e.lifecycleStage AS stage ORDER BY actor,participation"
    actual=[tuple(norm(v) for v in r.values()) for r in session.run(q,companies=companies,cutoff=report['cutoff'])];assert actual==expected
    report['basicChecks']['supplierContracts']={'passed':True,'rows':len(actual),'sample':actual[:10],'unsupported':['contract amount/product numeric feature filtering','authoritative current contract state']};save()
    eventids=list(dict.fromkeys(r[2] for r in actual))[:20]
    c.execute("SELECT e.evidence_id::text,a.document_id,e.source_event_id FROM event_evidence e JOIN document_assertion a USING(assertion_id) JOIN news_document n USING(document_id) JOIN document d USING(document_id) WHERE e.source_event_id=ANY(%s) AND d.available_at<=%s ORDER BY 1",(eventids,report['cutoff']));expected=c.fetchall()
    q='MATCH (n:NewsArticle)-[r:NewsArticle_DescribesEvent_SourceEvent]->(e:SourceEvent) WHERE e.id IN $events AND n.availableAt<=datetime($cutoff) RETURN r.key_0 AS evidence,n.id AS document,e.id AS event ORDER BY evidence'
    actual=[tuple(r.values()) for r in session.run(q,events=eventids,cutoff=report['cutoff'])];assert actual==expected
    report['basicChecks']['contractEvidence']={'passed':True,'rows':len(actual),'eventsRequested':len(eventids)};save()
    c.execute("SELECT c.actor_id FROM company_profile c JOIN equity_profile e ON e.issuer_actor_id=c.actor_id JOIN instrument i USING(instrument_id) WHERE i.ticker='012450'");company=c.fetchone()[0]
    c.execute('SELECT id,metric,value,unit,fs_basis,fiscal_period,period_kind,derivation,reporting_context_id,reported_snapshot_id FROM ontology_view.financial_metric WHERE company_id=%s AND available_at<=%s ORDER BY id',(company,report['cutoff']));expected=c.fetchall()
    q='MATCH (m:FinancialMetric)-[:FinancialMetric_ForCompany_Company]->(c:Company) WHERE c.id=$company AND m.availableAt<=datetime($cutoff) RETURN m.id AS id,m.metric AS metric,m.value AS value,m.unit AS unit,m.fsBasis AS basis,m.fiscalPeriod AS period,m.periodKind AS kind,m.derivation AS derivation ORDER BY id'
    rows=list(session.run(q,company=company,cutoff=report['cutoff']))
    actual=[tuple(Decimal(v) if k=='value' and v is not None else v for k,v in r.items()) for r in rows]
    assert actual==[r[:8] for r in expected]
    available=sorted({r[1] for r in expected})
    report['basicChecks']['F01Prerequisites']={'passed':True,'company':company,'rows':len(actual),'availableMetrics':available,'costStructureAnswerable':False,'missing':['cost of goods sold breakdown','fixed/variable cost classification','production quantity','contribution margin inputs'],'noOperatingLeverageEstimate':True};save()
report['basicChecksPassed']=True;save();print(json.dumps({'basicChecksPassed':True,'fullCqPassed':False}))
