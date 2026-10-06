"""Freeze purpose-use opportunities before the main agent evaluation, never from observed traces."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
# These are evaluation mappings, never agent instructions or prescribed traversal paths.
SCOPE={
 'CQ01':[
  ('직접 구성과 기업별 원비중 중복을 비교','ETF ETFHolding Equity Company','ETFHolding_ForETF_ETF ETFHolding_HoldsSecurity_Equity Company_Issues_Equity'),
  ('업종 체계 차이와 확인 가능한 업종 집중을 비교','SecurityIndustryClassification ExchangeSecurityClassification',''),
  ('미해소 보유와 하위 ETF를 구분','ETFHolding ETF','ETFHolding_HoldsSecurity_ETF')],
 'CQ02':[
  ('동일 날짜 가격과 좌당 NAV 차이를 계산','ETF DailyBar DailyNAV','DailyBar_ForSecurity_ETF DailyNAV_ForETF_ETF'),
  ('장중 추정과 마감 수급의 대상·단위를 구분','IntradayInvestorFlow DailyInvestorFlow Equity',''),
  ('환율·금리 변동 전제를 관측으로 확인','MacroObservation','')],
 'CQ03':[
  ('공급자와 거래 상대방의 실제 역할 확인','Company Organization SourceEvent','Company_ParticipatesIn_SourceEvent Organization_ParticipatesIn_SourceEvent'),
  ('보고 금액·기간의 뜻과 원문 확인','EventMeasurement NewsArticle Disclosure','EventMeasurement_ForEvent_SourceEvent NewsArticle_DescribesEvent_SourceEvent Disclosure_DescribesEvent_SourceEvent'),
  ('신규·변경·취소와 동일성 한계를 확인','SourceEvent EventThread','SourceEvent_InEventThread_EventThread')],
 'CQ04':[
  ('동일 회계 범위·기간의 보고값을 비교','Company FinancialMetric FinancialReportSnapshot','FinancialMetric_ForCompany_Company'),
  ('사업부문 설명의 기간·분모 한계를 확인','ReportedBusinessSegment Disclosure','ReportedBusinessSegment_DisclosedIn_Disclosure'),
  ('계산 입력과 정정 판본의 차이를 확인','FinancialMetric FinancialReportSnapshot','FinancialMetric_CalculatedFrom_FinancialMetric')],
 'CQ05':[
  ('실제 보유 사업과 원비중으로 전망 대상 결정','ETF ETFHolding Equity Company ReportedBusinessSegment','ETFHolding_ForETF_ETF Company_Issues_Equity'),
  ('사건 조건과 재무·시장 자료로 한 달 전망 근거 확인','SourceEvent EventMeasurement FinancialMetric DailyBar MacroObservation','Company_ParticipatesIn_SourceEvent EventMeasurement_ForEvent_SourceEvent'),
  ('과거 기대와 반대 근거를 대조해 판단 변경 조건 설명','ETFOutlookReport NewsArticle Disclosure','ETFOutlookReport_ForETF_ETF')],
 'CQ06':[
  ('펀드와 구성종목의 관측 가격 변동 확인','ETF ETFHolding Equity DailyBar','DailyBar_ForSecurity_ETF DailyBar_ForSecurity_Equity'),
  ('당시 소식·수급·시장 상황으로 원인 후보 확인','NewsArticle SourceEvent DailyInvestorFlow MacroObservation','NewsArticle_MentionsSecurity_Equity'),
  ('이전 가격 설명의 주장과 새 사실을 구분','ETFPriceExplanation NewsArticle','ETFPriceExplanation_ForETF_ETF')],
 'CQ07':[
  ('보유 기업이 해당 사건의 지정 역할인지 확인','ETFHolding Equity Company Organization SourceEvent','Company_Issues_Equity Company_ParticipatesIn_SourceEvent Organization_ParticipatesIn_SourceEvent'),
  ('같은 사건의 금액·기간·단위로 조건 판정','EventMeasurement SourceEvent','EventMeasurement_ForEvent_SourceEvent'),
  ('조건 충족과 미확인을 원문 근거로 구분','NewsArticle Disclosure','NewsArticle_DescribesEvent_SourceEvent Disclosure_DescribesEvent_SourceEvent')],
 'CQ08':[
  ('이전 설명과 그 당시 근거를 확인','ETFOutlookReport ETFPriceExplanation','ETFOutlookReport_ForETF_ETF ETFPriceExplanation_ForETF_ETF'),
  ('새 발생·새 확보·정정·재보도를 구분','SourceEvent EventThread NewsArticle','SourceEvent_InEventThread_EventThread'),
  ('새 사실이 기존 주장을 바꾸는지 확인','EventMeasurement FinancialMetric Disclosure','EventMeasurement_ForEvent_SourceEvent')],
 'CQ09':[
  ('사건 당시 보유 구성과 비중 확인','ETF ETFHolding Equity','ETFHolding_ForETF_ETF ETFHolding_HoldsSecurity_Equity'),
  ('현재 구성을 당시 구성과 구분','ETF ETFHolding Equity','ETFHolding_ForETF_ETF'),
  ('사건 참여 기업과 발행 증권을 정확히 연결','Company SourceEvent Equity','Company_Issues_Equity Company_ParticipatesIn_SourceEvent')],
 'CQ10':[
  ('전체 직접 보유 집합과 미확인 보유를 보존','ETF ETFHolding Equity','ETFHolding_ForETF_ETF ETFHolding_HoldsSecurity_Equity'),
  ('동일 가격 기준으로 전 구성종목 변동 계산','DailyBar Equity','DailyBar_ForSecurity_Equity'),
  ('상승·하락·보합·미확인을 원비중으로 요약','ETFHolding DailyBar','')],
 'CQ11':[
  ('발표한 계획과 당사자 역할 확인','Company Organization SourceEvent','Company_ParticipatesIn_SourceEvent Organization_ParticipatesIn_SourceEvent'),
  ('후속 계약·착수·실행을 발표와 구분','EventThread SourceEvent','SourceEvent_InEventThread_EventThread'),
  ('실행 규모와 원문이 확인하는 범위 설명','EventMeasurement NewsArticle Disclosure','EventMeasurement_ForEvent_SourceEvent')],
 'CQ12':[
  ('실제 실적의 회계·기간·단위를 확인','FinancialMetric FinancialReportSnapshot','FinancialMetric_ForCompany_Company'),
  ('발표 직전 동일 기준 기대와 가용시각 확인','SourceEvent EventMeasurement','EventMeasurement_ForEvent_SourceEvent'),
  ('비교 가능한 기대 차이와 비교 불가를 구분','FinancialMetric SourceEvent','')],
 'CQ13':[
  ('전망의 핵심 전제와 실제 보유 노출 확인','ETFOutlookReport ETFHolding Company','ETFOutlookReport_ForETF_ETF Company_Issues_Equity'),
  ('전제에 반하는 사건·재무·시장 자료를 탐색','SourceEvent FinancialMetric DailyBar MacroObservation','Company_ParticipatesIn_SourceEvent'),
  ('반증의 의미와 전망 수정 여부를 근거로 판정','EventMeasurement NewsArticle Disclosure','EventMeasurement_ForEvent_SourceEvent')],
}


if __name__=='__main__':
    target=APP/'data/cq-coverage-contract.json'
    if target.exists():raise ValueError('Frozen coverage contract already exists; do not overwrite after evaluation')
    cases=json.loads((APP/'data/cq-cases.json').read_text(encoding='utf8'))
    entries=[]
    for case,opportunities in SCOPE.items():
        weight=3 if case in ('CQ05','CQ06') else 2 if case in ('CQ07','CQ08','CQ10','CQ11') else 1
        for i,(purpose,objects,links) in enumerate(opportunities,1):
            entries.append({'id':case+'-'+str(i),'cq':case,'purpose':purpose,'weight':weight,
                'candidate_objects':objects.split(),'candidate_links':links.split(),
                'credit_rule':'Final claim, justified selection/exclusion or counterevidence decision must cite concrete returned objects and links. Schema reads and unrelated retrieval earn zero. Equivalent paths allowed.',
                'data_availability':'to_be_verified','grade':'not_evaluated'})
    result={'version':1,'frozen_at':datetime.now(timezone.utc).isoformat(),'target':0.8,
        'canonical_question_sha256':cases['question_source_sha256'],
        'definition':'Purpose-specific data use, not row counts, source counts or types merely queried.',
        'scoring':'Each purpose opportunity earns its weight only when the required meaning is demonstrated with returned evidence. Missing data remain in the requested denominator; available-data coverage is additional. Report unweighted sensitivity too.',
        'scope_note':'13 Korean equity-theme CQ scenarios; not coverage of all database rows or all industries. Pilots are excluded. Candidate paths are alternatives, not compulsory traversal instructions.',
        'opportunities':entries}
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'opportunities':len(entries),'weight':sum(e['weight'] for e in entries),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
