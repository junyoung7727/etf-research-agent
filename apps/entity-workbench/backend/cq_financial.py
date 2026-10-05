"""Comparable financial and macro evidence; report absent semantic dimensions explicitly."""
from decimal import Decimal
from backend.cq_tools import SELECTOR,STRING,LIMIT,RESULT_REF


class FinancialTools:
    def __init__(self,tools):
        self.tools=tools;self.graph=tools.graph
        tools.register('list_macro_series','Discover macro series actually present and available in the graph, including exact IDs, readable names, units, providers and observed dates. A failed name search does not establish missing data.',{},[],self.series)
        tools.register('get_financial_observations','Read company financials or reported segments for a batch or all ETF issuers. Preserve accounting scope, fiscal period, source/derived distinction and revision IDs. Guidance is source-event evidence; it is not automatically consensus.',
            {'targets':SELECTOR,'kind':{'enum':['actual','segment','guidance','consensus']},
             'fiscal_years':{'type':'array','items':{'type':'integer','minimum':1900,'maximum':2100}},
             'metrics':{'type':'array','items':STRING},'fs_basis':STRING,'limit':LIMIT},['targets','kind'],self.observations)
        tools.register('get_macro_observations','Read available macro time series over exact observation dates. Values, unit, vendor, series and availability are returned without inferring causation.',
            {'start_date':STRING,'end_date':STRING,'series_ids':{'type':'array','items':STRING},'query':{'type':'string'},'limit':LIMIT},
            ['start_date','end_date'],self.macro)
        tools.register('compare_observations','Compare two stored financial or macro observation IDs only when identity, metric, unit, accounting scope and period kind match. Return tool-calculated difference and positive-denominator change ratio.',
            {'dataset_ref':RESULT_REF,'earlier_id':STRING,'later_id':STRING},['dataset_ref','earlier_id','later_id'],self.compare)
        tools.register('derive_financial_period','Derive a fourth-quarter additive flow from full-year minus nine-month observations with the same company, year, unit, accounting scope and compatible reporting revision. Never derive EPS or balances this way.',
            {'dataset_ref':RESULT_REF,'annual_id':STRING,'nine_month_id':STRING},['dataset_ref','annual_id','nine_month_id'],self.derive)
        tools.register('compare_actual_to_expectation','Compare actual and pre-announcement expected observations only when both carry explicit identical metric, fiscal period, unit, currency and accounting scope. Reject event values lacking those dimensions.',
            {'actual_ref':RESULT_REF,'actual_id':STRING,'expectation_ref':RESULT_REF,'expectation_id':STRING},
            ['actual_ref','actual_id','expectation_ref','expectation_id'],self.expectation)

    def observations(self,targets,kind,fiscal_years=None,metrics=None,fs_basis=None,limit=20):
        selection=self.tools.select(targets);actors,mapping=self.tools.actors(selection)
        companies=[a for a in actors if a['object_type']=='Company']
        if kind=='actual':
            conditions=[];params={}
            for key,value in [('fiscalYear',fiscal_years),('metric',metrics),('fsBasis',fs_basis)]:
                if value:
                    conditions.append('n.'+key+(' IN $' if isinstance(value,list) else '=$')+key);params[key]=value
            rows=self.graph.linked(companies,'FinancialMetric_ForCompany_Company','reverse',where=' AND '.join(conditions) or None,parameters=params)
            items=[{**row['target'],'company_ref':row['source']} for row in rows]
        elif kind=='segment':
            if fiscal_years or metrics or fs_basis:raise ValueError('Segment fiscal/accounting dimensions are not mapped; these filters cannot be honored')
            docs=self.graph.linked(companies,'Company_HasDisclosure_Disclosure')
            refs=[{k:r['target'][k] for k in ('object_type','object_id')} for r in docs]
            rows=self.graph.linked(refs,'ReportedBusinessSegment_DisclosedIn_Disclosure','reverse')
            items=[row['target'] for row in rows]
        elif kind in ('guidance','consensus'):
            if fiscal_years or metrics or fs_basis:raise ValueError('Comparable expectation fiscal/accounting dimensions are not yet mapped')
            if kind=='consensus':
                return self.tools.result([],selection=selection,scope={'dataset_kind':'financial_observations','kind':kind,
                    'availability':'unsupported','reason':'The graph contains no typed consensus observations. Source-event guidance cannot be relabeled consensus.'})
            events={}
            for row in self.graph.linked(companies,'Company_ParticipatesIn_SourceEvent',where="n.eventType='COMPANY.EARNINGS.GUIDANCE_CHANGE'"):
                events[row['target']['object_id']]=row['target']
            items=self.tools.events.enrich(list(events.values()))
            return self.tools.result(items,selection=selection,scope={'dataset_kind':'guidance_events','comparison_ready':False,
                'reason':'Event evidence lacks complete fiscal period/accounting/currency dimensions for comparable expected financials'},
                display_items=[self.tools.events.display(x) for x in items],limit=min(limit,20))
        else:raise ValueError('Unsupported financial kind')
        return self.tools.result(items,selection=selection,scope={'dataset_kind':'financial_observations','kind':kind,
            'actor_mapping':mapping,'revisions':'all matching stored versions; no arbitrary latest selection'},limit=limit)

    def macro(self,start_date,end_date,series_ids=None,query='',limit=20):
        if self.tools.check_date(start_date)>self.tools.check_date(end_date):raise ValueError('Invalid dates')
        items=self.graph.nodes('MacroObservation',query=query,filters={'seriesId':series_ids} if series_ids else {},
            where='n.observationDate>=date($start) AND n.observationDate<=date($end)',parameters={'start':start_date,'end':end_date})
        return self.tools.result(items,scope={'dataset_kind':'macro_observations','start_date':start_date,'end_date':end_date},limit=limit)

    def observation(self,ref,identifier):
        data=self.tools.store.reference(ref,'dataset')
        rows=[x for x in data['items'] if x.get('object_id')==identifier]
        if len(rows)!=1:raise ValueError('Select one unambiguous observation from this stored dataset')
        return rows[0],data

    def series(self):
        rows=self.graph.query('MATCH (n:MacroObservation) WHERE n.availableAt<=datetime($cutoff) '
            'RETURN n.seriesId AS series_id,n.seriesName AS name,n.unit AS unit,n.sourceVendor AS provider,'
            'min(n.observationDate) AS first_date,max(n.observationDate) AS last_date ORDER BY series_id',
            {'cutoff':self.tools.store.cutoff},objects=['MacroObservation'])
        return self.tools.result(rows,scope={'dataset_kind':'available_macro_series'},limit=100)

    @staticmethod
    def comparable(a,b,keys):
        for key in keys:
            if a.get(key) is None or b.get(key) is None or a[key]!=b[key]:
                raise ValueError('Missing or mismatched comparison dimension: '+key)
        if a.get('value') is None or b.get('value') is None:raise ValueError('Comparison value is missing')
        x,y=Decimal(a['value']),Decimal(b['value'])
        if not x.is_finite() or not y.is_finite():raise ValueError('Comparison values must be finite')
        return x,y

    def compare(self,dataset_ref,earlier_id,later_id):
        a,data=self.observation(dataset_ref,earlier_id);b,_=self.observation(dataset_ref,later_id)
        if a['object_type']!=b['object_type']:raise ValueError('Observation types differ')
        if a['object_type']=='FinancialMetric':
            keys=['corpCode','metric','unit','fsBasis','periodKind','derivation']
            # Three-month and six-month cumulative revenue are different durations.
            if a['properties'].get('periodKind') in ('CUMULATIVE','YTD'):
                keys.append('fiscalPeriod')
            before=a['properties'].get('periodEnd');after=b['properties'].get('periodEnd')
        elif a['object_type']=='MacroObservation':
            keys=['seriesId','unit'];before=a['properties'].get('observationDate');after=b['properties'].get('observationDate')
        else:raise ValueError('Unsupported comparison object')
        if not before or not after or before>=after:raise ValueError('Earlier/later observation dates must be ordered')
        x,y=self.comparable(a['properties'],b['properties'],keys)
        return self.tools.result([{'earlier_id':earlier_id,'later_id':later_id,'difference':str(y-x),
            'change_ratio':str(y/x-1) if x>0 else None,'ratio_reason':None if x>0 else 'nonpositive_denominator',
            'unit':a['properties']['unit']}],selection=data.get('selection'),scope={'dataset_kind':'observation_comparison','input_ref':dataset_ref})

    def derive(self,dataset_ref,annual_id,nine_month_id):
        a,data=self.observation(dataset_ref,annual_id);b,_=self.observation(dataset_ref,nine_month_id)
        if a['object_type']!='FinancialMetric' or b['object_type']!='FinancialMetric':raise ValueError('FinancialMetric inputs required')
        p,q=a['properties'],b['properties']
        if p.get('metric') not in ('revenue','operating_income','net_income','REVENUE','OPERATING_INCOME','NET_INCOME'):
            raise ValueError('Only verified additive financial flow metrics may be differenced')
        if p.get('fiscalPeriod')!='FY' or q.get('fiscalPeriod') not in ('9M','Q3') or q.get('periodKind') not in ('YTD','CUMULATIVE'):
            raise ValueError('Verified full-year and cumulative nine-month periods required')
        x,y=self.comparable(p,q,['corpCode','metric','unit','fsBasis','fiscalYear'])
        if not p.get('rceptNo') or p.get('rceptNo')!=q.get('rceptNo'):
            raise ValueError('Cross-report revision compatibility is not established; choose compatible inputs')
        return self.tools.result([{'value':str(x-y),'metric':p['metric'],'unit':p['unit'],'fiscal_period':'Q4',
            'formula':'FY - 9M','input_ids':[annual_id,nine_month_id]}],selection=data.get('selection'),scope={'dataset_kind':'derived_financial','input_ref':dataset_ref})

    def expectation(self,actual_ref,actual_id,expectation_ref,expectation_id):
        a,data=self.observation(actual_ref,actual_id);e,expected=self.observation(expectation_ref,expectation_id)
        if expected['scope'].get('dataset_kind')!='expected_financial_observations':
            raise ValueError('No comparable expected-financial dataset; event amounts are not consensus')
        p,q=a['properties'],e['properties']
        if not p.get('availableAt') or not q.get('availableAt') or q['availableAt']>=p['availableAt']:
            raise ValueError('Expectation must be available strictly before the actual announcement')
        actual,estimate=self.comparable(p,q,['corpCode','metric','unit','currencyCode','fsBasis','fiscalYear','fiscalPeriod','periodKind'])
        return self.tools.result([{'difference':str(actual-estimate),'difference_ratio':str(actual/estimate-1) if estimate>0 else None,
            'ratio_reason':None if estimate>0 else 'nonpositive_expected_value','unit':p['unit'],
            'input_ids':[actual_id,expectation_id]}],selection=data.get('selection'),scope={'input_refs':[actual_ref,expectation_ref]})
