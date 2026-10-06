"""Material portfolio arithmetic over saved holdings; never infer rebalancing."""
from decimal import Decimal
from backend.cq_tools import RESULT_REF,REFS


class HoldingCalculations:
    def __init__(self,tools):
        self.tools=tools
        tools.register('summarize_etf_holdings','Calculate original holding weight sums for all constituents, an explicit subset or the largest N holdings. Use for material concentration and event exposure numbers. No inferred corporate groups or normalization.',
            {'selection_ref':RESULT_REF,'members':REFS,'top_n':{'type':'integer','minimum':1,'maximum':1000}},['selection_ref'],self.summarize)
        tools.register('compare_holdings_dates','Compare saved snapshots of the same ETF on ordered dates. Weight changes do not prove manager trades or rebalancing.',
            {'earlier_ref':RESULT_REF,'later_ref':RESULT_REF},['earlier_ref','later_ref'],self.compare)

    def selection(self,ref):
        result=self.tools.store.reference(ref,'selection')
        if not result.get('etf_ref') or not result.get('selected_date'):raise ValueError('A nonempty dated ETF holdings selection is required')
        return result

    def summarize(self,selection_ref,members=None,top_n=None):
        selection=self.selection(selection_ref);rows=selection['items']
        if members is not None and top_n is not None:raise ValueError('Choose an explicit subset or top N, not both')
        keys={(r['object_type'],r['object_id']) for r in rows}
        if members is not None:
            requested={(r['object_type'],r['object_id']) for r in members}
            if not requested<=keys:raise ValueError('A requested member is not in this saved holding snapshot')
            rows=[r for r in rows if (r['object_type'],r['object_id']) in requested]
        if top_n is not None:
            if any(r.get('weight_ratio') is None for r in rows):raise ValueError('Unknown weights prevent ranking the largest holdings')
            rows=sorted(rows,key=lambda r:(-Decimal(str(r['weight_ratio'])),r['object_id']))[:top_n]
        known=[Decimal(str(r['weight_ratio'])) for r in rows if r.get('weight_ratio') is not None]
        if any(not w.is_finite() or w<0 for w in known):raise ValueError('Invalid holdings weights')
        total=sum(known,Decimal(0))
        return self.tools.result([{'raw_weight_sum':str(total),'weight_percent':str(total*100),
            'member_refs':[{k:r[k] for k in ('object_type','object_id')} for r in rows],
            'unknown_weights':sum(r.get('weight_ratio') is None for r in rows),
            'status':'partial' if len(known)!=len(rows) else 'calculated',
            'holding_ids':[r.get('holding_id') for r in rows]}],selection=selection,
            scope={'dataset_kind':'holding_weight_summary','input_ref':selection_ref,'selected_date':selection['selected_date'],
                'interpretation':'Sum of stored direct holding weights; not profit exposure, return attribution or certified full-fund completeness.'})

    def compare(self,earlier_ref,later_ref):
        a=self.selection(earlier_ref);b=self.selection(later_ref)
        if a['etf_ref']!=b['etf_ref']:raise ValueError('Date comparison requires the same ETF')
        if a['selected_date']>=b['selected_date']:raise ValueError('Earlier and later actual dates must be ordered')
        left={(r['object_type'],r['object_id']):r for r in a['items']};right={(r['object_type'],r['object_id']):r for r in b['items']}
        rows=[]
        for key in sorted(left.keys()|right.keys(),key=str):
            x=left.get(key);y=right.get(key);v=x.get('weight_ratio') if x else None;w=y.get('weight_ratio') if y else None
            delta=Decimal(str(w))-Decimal(str(v)) if v is not None and w is not None else None
            rows.append({'object_type':key[0],'object_id':key[1],'earlier_present':x is not None,'later_present':y is not None,
                'earlier_weight':v,'later_weight':w,'weight_change':str(delta) if delta is not None else None,
                'percentage_point_change':str(delta*100) if delta is not None else None,
                'earlier_holding_id':x.get('holding_id') if x else None,'later_holding_id':y.get('holding_id') if y else None})
        return self.tools.result(rows,scope={'dataset_kind':'holding_date_comparison','input_refs':[earlier_ref,later_ref],
            'earlier_date':a['selected_date'],'later_date':b['selected_date'],
            'interpretation':'Presence within stored snapshots. Missing rows are not certified zero holdings. Weight differences do not identify manager trades.'},limit=100)
