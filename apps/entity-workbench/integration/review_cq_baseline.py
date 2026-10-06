"""Persist human/model judgment of completed answers, supported by saved tool evidence.

This is a recorded review, not an automatic grader. Merely executing a tool earns no credit.
"""
import json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]/'output/cq-tools-benchmark-20261005'
# Reviewed full answers and retained calculator/source responses, 2026-10-06 KST.
REVIEWS={
 'CQ01':('needs_improvement',[2],['비교할 두 번째 ETF 자료가 없어 기업 중복·분산 목적을 달성하지 못했다.','상위 보유 비중 합계를 에이전트가 직접 계산했다. 업종 체계 차이와 분류 결측은 구분했다.']),
 'CQ02':('needs_improvement',[1,3],['가격·NAV 계산과 원화 약세·금리 상승 전제 반박에는 실제 계산 근거가 있다.','장중 구간 의미가 미확인인데 누적 추정치라고 단정했고, 같은 대상의 장중·마감 비교가 빠졌다.']),
 'CQ03':('needs_improvement',[1,2],['당사자·금액·기간의 서로 다른 보도를 확인했다.','이전 검색 미발견을 신규 계약의 확정 근거로 사용했다. 출처 개수도 불필요하게 답변에 넣었다.']),
 'CQ04':('data_limited',[1],['동일 연결·단일 분기 보고값의 증가액·증가율은 저장된 계산 결과와 일치했다.','사업부문 자료가 없다는 한계를 드러냈다. 실제 정정 판본·파생 입력의 검증은 완료되지 않았다.']),
 'CQ05':('failed',[],['핵심 노출 비중을 에이전트가 합산했고 수급의 억원·십억원 표현이 모순됐다.','우선협상 선정을 첫 문장에서 확정 수주로 과장했다.','마감 후 보도라 가격에 미반영됐다고 단정했고, 이름 검색 실패를 거시자료 부재로 확대했다.']),
 'CQ06':('needs_improvement',[1,2],['가격·NAV와 장중 선행 보도, 이후 확인 보도를 구분했다. 관측과 인과 확정을 구분했다.','이전 설명의 요약은 조회했으나 당시 근거가 해소되지 않아 과거 주장 수정 전체를 검증하지 못했다.']),
 'CQ07':('needs_improvement',[1,2],['공급자 역할·총액·단위의 조건을 같은 사건으로 확인했다.','후속 기록 미발견으로 현재 확정 상태가 유지된다고 단정했다. 요청한 계약기간·원문 근거 제시도 부족했다.']),
 'CQ08':('needs_improvement',[],['요청 기준일에 이전 설명이 없는데 후일 설명을 대체 기준으로 사용했다.','20일선 상태를 새로 계산하지 않고 현재 상태로 단정했고, 장중 선행 보도를 놓쳐 신규 정보의 시점을 잘못 설명했다.']),
 'CQ09':('needs_improvement',[1,2,3],['사건 당시와 현재의 실제 날짜별 보유·기업·증권을 확인했다. 단순 구성 일치 여부는 자료에서 읽을 수 있다.','중요 비중 변화율은 날짜 비교 도구가 거부한 뒤 직접 계산했다. 이 추가 주장은 별도 실패다.']),
 'CQ10':('needs_improvement',[1,2,3],['전체 10개 대상의 관측 종가 변화와 방향별 원비중은 계산 도구가 검증했다.','추가한 NAV 증가율에는 계산 도구 근거가 없고, 조정 기준 미확인을 미조정으로 표현했다.']),
 'CQ11':('passed',[1,2,3],['발표 예정·실제 서명·납품 실행을 구분했다. 원문의 예정 표현과 구조화 단계가 충돌한 기록을 배제했다.','납품 기록 미발견을 실행 부재로 단정하지 않았고 금액 충돌·읽은 범위를 밝혔다. 이 입력 사례의 목적을 충족했다.']),
 'CQ12':('data_limited',[1],['동일 기간·회계 범위의 실제 실적은 확인했지만 비교 가능한 발표 전 기대 자료가 없다.','기대 초과·미달을 단정하지 않은 것은 올바른 제한이나, 기대 비교 목적을 달성한 것으로 채점하지 않는다.']),
 'CQ13':('needs_improvement',[2],['규제·중재와 미확정 사업 단계라는 반대 근거를 찾았다.','중요 노출 비중을 직접 합산했고 20일선 위치를 재계산 없이 재사용했다. 거시 검색 실패를 자료 부재로 설명했다.']),
}
PROOF_TOOLS={
 'CQ01':['get_security_classifications','get_linked_objects'],
 'CQ02':['calculate_nav_premium','compare_observations'],
 'CQ03':['search_events','read_documents'],
 'CQ04':['compare_observations','get_financial_observations'],
 'CQ06':['calculate_returns','calculate_nav_premium','read_documents','get_flow_observations'],
 'CQ07':['search_events'],
 'CQ09':['get_etf_holdings','read_documents','search_events'],
 'CQ10':['calculate_returns','summarize_price_breadth'],
 'CQ11':['get_etf_holdings','search_events','read_documents','get_event_history'],
 'CQ12':['get_financial_observations'],
 'CQ13':['read_documents','search_events']}


if __name__=='__main__':
    contract=json.loads((Path(__file__).resolve().parents[1]/'data/cq-coverage-contract.json').read_text(encoding='utf8'))
    evaluated=[]
    for case,(grade,credits,findings) in REVIEWS.items():
        paths=sorted((ROOT/'agent-runs').glob(case+'-suite*/benchmark.json'))
        if len(paths)!=1:raise ValueError('Baseline must have one fixed run per CQ')
        path=paths[0];report=json.loads(path.read_text(encoding='utf8'))
        if report['status']!='answered':raise ValueError('Incomplete baseline')
        proofs=[]
        for p in (path.parent/'tools').glob('*.json'):
            t=json.loads(p.read_text(encoding='utf8'))
            if not t['error'] and t['tool'] in PROOF_TOOLS.get(case,[]):
                proofs.append({'tool_run_id':t['response']['tool_run_id'],'tool':t['tool']})
        review={'reviewed_at':datetime.now(timezone.utc).isoformat(),'method':'Manual semantic review of answer and saved evidence',
            'findings':findings,'credited_opportunities':[case+'-'+str(i) for i in credits],
            'supporting_tool_runs':proofs,'scope':'One real input per CQ, not all canonical adversarial variants'}
        report.update(semantic_grade=grade,review=review)
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        evaluated.append({'case':case,'run_id':path.parent.name,'grade':grade,'review':review})
    credit={i for r in evaluated for i in r['review']['credited_opportunities']}
    earned=sum(o['weight'] for o in contract['opportunities'] if o['id'] in credit)
    total=sum(o['weight'] for o in contract['opportunities'])
    report={'stage':'initial_baseline','cases':evaluated,'purpose_checklist':{
        'earned_weight':earned,'total_weight':total,'ratio':earned/total,'target':0.8,
        'credited_opportunities':len(credit),'opportunity_count':len(contract['opportunities']),
        'unweighted_ratio':len(credit)/len(contract['opportunities']),
        'definition':'보조 지표: 의미 검토에서 충족한 목적별 확인 항목. 객체·링크 각각의 실사용 커버리지와 동일하지 않다.','scope':contract['scope_note']},
        'requested_scope_coverage':{'status':'not_measured','target':0.8,
            'reason':'Each object/link use needs its own verified purpose and concrete evidence. The 39-purpose checklist alone cannot establish ontology data coverage.'},
        'available_data_coverage':{'status':'not_certified','reason':'Unavailable scope has not been independently classified for every opportunity; requested denominator is retained.'},
        'quality_note':'Useful evidence use can earn coverage even when an unrelated additional claim makes the whole answer fail. Coverage is not answer correctness.'}
    (ROOT/'baseline-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'graded_cases':len(evaluated),'weighted_coverage':earned/total,'unweighted_coverage':len(credit)/len(contract['opportunities'])}))
