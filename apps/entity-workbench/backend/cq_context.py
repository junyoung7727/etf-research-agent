"""Batch discovery of document context and security classifications through graph links."""
from decimal import Decimal
from backend.cq_tools import SELECTOR,STRING,LIMIT,RESULT_REF

FACTORS={'industry':'SecurityIndustryClassification','exchange_classification':'ExchangeSecurityClassification',
         'listing':'SecurityListingSnapshot','market_capitalization':'MarketCapitalization'}


class ContextTools:
    def __init__(self,tools):
        self.tools=tools;self.graph=tools.graph
        tools.register('search_documents','Find articles and disclosures through selected securities, issuing companies or related events. Distinguish mentions, issuer filings and event evidence. Search currently available titles/excerpts; no full-body search claim.',
            {'targets':SELECTOR,'query':{'type':'string'},'kinds':{'type':'array','items':{'enum':['NewsArticle','Disclosure']},'minItems':1},
             'start_date':STRING,'end_date':STRING,'limit':LIMIT},['start_date','end_date'],self.documents)
        tools.register('get_security_classifications','Read selected securities with available industry, exchange classification, listing and market capitalization records. Missing/uncertain values remain explicit; classifications are not investment factors.',
            {'targets':SELECTOR,'factors':{'type':'array','items':{'enum':list(FACTORS)},'minItems':1},'limit':LIMIT},['targets','factors'],self.factors)
        tools.register('get_instrument_factors','Gather graph evidence for chart, finalized flow, valuation inputs and shared macro context for the selected securities. Shared macro is read once. Derived indicators require their calculation tools; raw observations are not precomputed factor scores.',
            {'targets':SELECTOR,'start_date':STRING,'end_date':STRING,
             'factors':{'type':'array','items':{'enum':['chart','flow','valuation','macro']},'minItems':1,'uniqueItems':True},'limit':LIMIT},
            ['targets','start_date','end_date','factors'],self.instrument_factors)
        tools.register('compare_etf_exposure','Compare two saved complete holding selections by exact security or issuing company identity. Sum original weights and minimum overlap weights without rescaling missing holdings.',
            {'left_ref':RESULT_REF,'right_ref':RESULT_REF,'group_by':{'enum':['security','company']}},['left_ref','right_ref','group_by'],self.exposure)
        tools.register('calculate_flow_totals','Sum one named daily investor quantity or monetary field across the stored date range, per security. Missing values remain partial; ETF constituent flows are not ETF investor flows.',
            {'dataset_ref':RESULT_REF,'field':{'enum':['netQtyIndividual','netValIndividual','netQtyForeign','netValForeign','netQtyInstitutionTotal','netValInstitutionTotal']}},
            ['dataset_ref','field'],self.flow_totals)
        tools.register('get_previous_analyses','Read published database-backed v2 ETF reports strictly before the requested time through ETF graph links. Preserve prior text and cutoff. Historical tool references currently cannot be resolved as new factual evidence.',
            {'etf_ref':{'type':'object','properties':{'object_type':{'const':'ETF'},'object_id':STRING},'required':['object_type','object_id'],'additionalProperties':False},
             'before':STRING,'kind':{'enum':['outlook','movement','both']},'limit':LIMIT},['etf_ref','before'],self.previous)

    def instrument_factors(self,targets,start_date,end_date,factors,limit=20):
        selection=self.tools.select(targets);items=[];scopes={}
        for factor in factors:
            if factor=='chart':result,dataset=self.tools.market.prices(targets,start_date,end_date,limit=limit)
            elif factor=='flow':result,dataset=self.tools.market.flows(targets,start_date,end_date,'daily',limit=limit)
            elif factor=='valuation':
                result,dataset=self.tools.financial.observations(targets,'actual',metrics=['eps_basic','bps','bps_total_shares'],limit=limit)
            else:result,dataset=self.tools.financial.macro(start_date,end_date,limit=limit)
            scopes[factor]=result['data_scope']
            items.extend({'factor':factor,'observation':row} for row in dataset['items'])
        return self.tools.result(items,selection=selection,scope={'dataset_kind':'factor_inputs','factor_scopes':scopes,
            'derived_factor_scores':'not calculated; this tool gathers inputs','shared_macro':'one query, not repeated per security'},limit=limit)

    def previous(self,etf_ref,before,kind='both',limit=20):
        from datetime import datetime
        stamp=datetime.fromisoformat(before.replace('Z','+00:00'))
        if stamp.tzinfo is None:raise ValueError('before must include a timezone')
        if stamp>datetime.fromisoformat(self.tools.store.cutoff):raise ValueError('before exceeds analysis cutoff')
        selection=self.graph.get([etf_ref]);items=[]
        kinds=['ETFOutlookReport','ETFPriceExplanation'] if kind=='both' else [{'outlook':'ETFOutlookReport','movement':'ETFPriceExplanation'}[kind]]
        for report_type in kinds:
            for row in self.graph.linked([etf_ref],report_type+'_ForETF_ETF','reverse',
                    where='n.analysisAt<datetime($before) AND n.availableAt<datetime($before)',parameters={'before':before}):
                items.append(row['target'])
        items.sort(key=lambda o:(o['properties'].get('analysisAt',''),o['object_id']),reverse=True)
        return self.tools.result(items,selection=selection,limit=limit,scope={'dataset_kind':'previous_analyses',
            'historical_evidence_resolution':'unavailable','interpretation':'Previous model interpretations, not observed facts','before':before})

    def documents(self,start_date,end_date,targets=None,query='',kinds=None,limit=20):
        if self.tools.check_date(start_date)>self.tools.check_date(end_date):raise ValueError('Invalid dates')
        if targets is None and not query:raise ValueError('A target selection or search text is required')
        kinds=kinds or ['NewsArticle','Disclosure'];items={};selection=None
        params=self.tools.time_bounds(start_date,end_date)
        where='n.publishedAt>=datetime($start_at) AND n.publishedAt<datetime($end_at)'
        def add(obj,reason):
            if obj['object_type'] not in kinds:return
            text=(obj['properties'].get('title') or '')+' '+(obj['properties'].get('leadText') or '')
            if query and query not in text:return
            key=(obj['object_type'],obj['object_id'])
            item=items.setdefault(key,{'document':obj,'connection_reasons':[]})
            if reason not in item['connection_reasons']:item['connection_reasons'].append(reason)
        if targets is None:
            for kind in kinds:
                for obj in self.graph.nodes(kind,query=query,where=where,parameters=params):add(obj,'text_search')
        else:
            selection=self.tools.select(targets);actors,_=self.tools.actors(selection)
            equities=[{k:r[k] for k in ('object_type','object_id')} for r in selection['items'] if r['status']=='resolved' and r['object_type']=='Equity']
            companies=[r for r in actors if r['object_type']=='Company']
            for row in self.graph.linked(equities,'NewsArticle_MentionsSecurity_Equity','reverse',where=where,parameters=params):add(row['target'],'security_mention')
            for row in self.graph.linked(companies,'Company_HasDisclosure_Disclosure',where=where,parameters=params):add(row['target'],'issuer_filing')
            for actor_type in ('Company','Organization'):
                ids=[r['object_id'] for r in actors if r['object_type']==actor_type]
                if not ids:continue
                for kind in kinds:
                    participation=actor_type+'_ParticipatesIn_SourceEvent';evidence=kind+'_DescribesEvent_SourceEvent'
                    statement=('MATCH (a:'+actor_type+')-[:'+participation+']->(e:SourceEvent)<-[:'+evidence+']-(n:'+kind+') '
                        'WHERE a.id IN $actors AND '+where+' AND e.availableAt<=datetime($cutoff) AND n.availableAt<=datetime($cutoff) '
                        'RETURN DISTINCT n.id AS id,properties(n) AS properties ORDER BY n.id LIMIT '+str(self.graph.max_rows+1))
                    rows=self.graph.query(statement,{**params,'actors':ids,'cutoff':self.tools.store.cutoff},
                        objects=[actor_type,'SourceEvent',kind],links=[participation,evidence])
                    for row in rows:add(self.graph.object(kind,{**row['properties'],'id':row['id']}),'event_evidence')
        ordered=[items[k] for k in sorted(items)]
        visible=[{'document_ref':{k:r['document'][k] for k in ('object_type','object_id')},'title':r['document']['title'],
            'published_at':r['document']['properties'].get('publishedAt'),'connection_reasons':r['connection_reasons']} for r in ordered]
        return self.tools.result(ordered,selection=selection,scope={'dataset_kind':'documents','search_scope':'titles and available excerpts',
            'start_date':start_date,'end_date':end_date,'query':query,'full_body_search':False},display_items=visible,limit=limit)

    def factors(self,targets,factors,limit=20):
        selection=self.tools.select(targets);output=[]
        for kind in ('Equity','ETF'):
            refs=[{k:r[k] for k in ('object_type','object_id')} for r in selection['items'] if r['status']=='resolved' and r['object_type']==kind]
            for factor in factors:
                object_type=FACTORS[factor];relation=object_type+'_ForSecurity_'+kind
                if relation not in self.graph.links:
                    # Some classification objects expose a differently named declared link.
                    matches=[r['id'] for r in self.graph.links.values() if r['source']==object_type and r['target']==kind]
                    if len(matches)!=1:raise ValueError('No unique declared factor path: '+factor+' / '+kind)
                    relation=matches[0]
                for row in self.graph.linked(refs,relation,'reverse'):
                    output.append({'security_ref':row['source'],'factor':factor,'observation':row['target']})
        return self.tools.result(output,selection=selection,scope={'dataset_kind':'instrument_factors','requested_factors':factors,
            'classification_dates':'snapshot/collection dates are not certified historical effective dates'},limit=limit)

    def exposure(self,left_ref,right_ref,group_by):
        left=self.tools.store.reference(left_ref,'selection');right=self.tools.store.reference(right_ref,'selection')
        for selection in (left,right):
            if 'etf_ref' not in selection:raise ValueError('ETF holdings selections required')
        if left.get('selected_date')!=right.get('selected_date') or not left.get('selected_date'):
            raise ValueError('Both holdings selections must have the same actual date')
        def group(selection):
            weights={};unknown=[]
            issuer_map={}
            if group_by=='company':
                _,mapping=self.tools.actors(selection)
                issuer_map={m['security']['object_id']:m['actor']['object_id'] for m in mapping}
            for item in selection['items']:
                if group_by=='security':key=(item['object_type'],item['object_id'])
                else:
                    key=('Company',issuer_map.get(item['object_id'])) if item['object_type']=='Equity' else (None,None)
                if item['status']!='resolved' or key[1] is None or item.get('weight_ratio') is None:
                    unknown.append(item['object_id']);continue
                weights[key]=weights.get(key,Decimal(0))+Decimal(str(item['weight_ratio']))
            return weights,unknown
        a,ua=group(left);b,ub=group(right)
        rows=[{'object_type':k[0],'object_id':k[1],'left_weight':str(a.get(k,0)),'right_weight':str(b.get(k,0)),
            'overlap_weight':str(min(a.get(k,Decimal(0)),b.get(k,Decimal(0))))} for k in sorted(a.keys()|b.keys())]
        result,dataset=self.tools.result(rows,scope={'dataset_kind':'exposure_comparison','group_by':group_by,
            'date':left['selected_date'],'input_refs':[left_ref,right_ref],'unresolved_left':ua,'unresolved_right':ub,
            'overlap_weight':str(sum((min(a.get(k,Decimal(0)),b.get(k,Decimal(0))) for k in a.keys()|b.keys()),Decimal(0))),
            'interpretation':'raw weight overlap; incomplete holdings cannot establish full fund diversification'},limit=100)
        return result,dataset

    def flow_totals(self,dataset_ref,field):
        data=self.tools.store.reference(dataset_ref,'dataset')
        if data['scope'].get('dataset_kind')!='flow_observations' or data['scope'].get('frequency')!='daily':
            raise ValueError('Only daily finalized flow datasets may be summed')
        rows=[]
        for member in data['selection']['items']:
            observations=[o for o in data['items'] if o['properties'].get('instrumentId')==member['object_id']]
            values=[Decimal(str(o['properties'][field])) for o in observations if o['properties'].get(field) is not None]
            currency=(member.get('object') or {}).get('properties',{}).get('currencyCode')
            unit='shares_or_units' if field.startswith('netQty') else currency
            rows.append({'object_id':member['object_id'],'field':field,'value':str(sum(values,Decimal(0))) if values and unit else None,
                'unit':unit,'observed_rows':len(observations),'missing_values':len(observations)-len(values),
                'status':'available_observations_only' if values and unit else 'unavailable',
                'input_ids':[o['object_id'] for o in observations]})
        return self.tools.result(rows,selection=data['selection'],scope={'dataset_kind':'flow_totals','input_ref':dataset_ref,
            'date_completeness':'Trading-calendar completeness is not certified; sums cover available observations only'},limit=100)
