"""Publish implemented entry points and actual support boundaries, never infer support from registration."""
import json
import sys
import tempfile
from pathlib import Path

APP=Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from backend.cq_tools import CQTools
from backend.view_design import read_catalog

PURPOSES={
 'get_ontology_schema':'객체·속성·관계의 뜻과 탐색 경계를 확인',
 'search_objects':'이름·속성 조건으로 실제 객체 후보 검색',
 'get_objects':'타입 있는 ID 목록을 한 번에 확인',
 'resolve_securities':'거래소·종목 코드 목록을 증권 객체와 일괄 연결',
 'get_linked_objects':'선언된 관계를 양방향으로 일괄 탐색',
 'get_result_page':'저장한 자료의 다음 페이지를 재조회 없이 읽음',
 'get_etf_holdings':'기준일의 직접 보유 구성 전체와 원비중 확인',
 'search_events':'참여 역할과 같은 사건의 수치·근거를 함께 검색',
 'get_event_history':'저장된 관련 사건과 후속 근거 확인',
 'read_documents':'확보된 제목·발췌를 읽고 읽은 범위를 표시',
 'get_price_observations':'대상 목록·ETF 전체의 일봉과 선택적 NAV 조회',
 'get_flow_observations':'대상별 마감 수급과 장중 추정을 구분해 조회',
 'calculate_returns':'저장된 두 날짜 가격으로 변화율 계산',
 'summarize_price_breadth':'전체 대상의 상승·하락·보합·미확인과 원비중 집계',
 'calculate_nav_premium':'같은 날짜·통화·좌당 가격과 NAV의 괴리 계산',
 'list_macro_series':'그래프에 실제 존재하는 거시지표 목록 발견',
 'get_financial_observations':'회사 재무·사업부문·기대 자료의 가용 범위 확인',
 'get_macro_observations':'시계열별 관측값·단위·가용시각 조회',
 'compare_observations':'비교 가능한 재무·거시 관측의 차이와 변화율 계산',
 'derive_financial_period':'검증된 연간·9개월 입력으로 단일 4분기 계산',
 'compare_actual_to_expectation':'발표 전 같은 기준의 기대와 실제 결과 비교',
 'search_documents':'종목 언급·공시 주체·사건 근거를 구분해 문서 검색',
 'get_security_classifications':'업종·시장 분류·상장·시장가치 자료 확인',
 'get_instrument_factors':'차트·수급·밸류·거시의 그래프 입력을 묶어 조회',
 'compare_etf_exposure':'동일 날짜 두 ETF의 종목·발행회사 비중 중복 계산',
 'calculate_flow_totals':'저장된 기간의 특정 투자자 수급을 대상별 합산',
 'get_previous_analyses':'ETF에서 이전 발행 전망·가격 설명 탐색',
 'summarize_etf_holdings':'전체·명시한 부분·상위 보유의 원비중 합계 계산',
 'compare_holdings_dates':'같은 ETF의 두 시점 보유 여부와 비중 차이 계산'}
LIMITS={
 'get_etf_holdings':('partial','한 호출 한 기준일. 전체 원천 스냅샷의 완전성은 인증되지 않음.'),
 'get_event_history':('partial','저장된 연결을 확인하며 실제 사건 동일성·현재 계약 유효성을 인증하지 않음.'),
 'read_documents':('partial','제목·확보 발췌만 제공. 전문은 현재 그래프에 없음.'),
 'get_financial_observations':('partial','구조화된 비교 가능 컨센서스 없음. 사업부문 기간·회계 범위 일부 미확정.'),
 'derive_financial_period':('conditional','동일 보고 판본 호환이 입증된 조합만 허용. 실제 교차 보고서 조합은 아직 미검증.'),
 'compare_actual_to_expectation':('unavailable_source','비교 가능한 발표 전 기대 관측이 그래프에 없어 실제 기대 비교 미지원.'),
 'get_instrument_factors':('partial','그래프 입력을 묶음. 기존의 모든 기술지표·밸류 스코어 계산은 이 구현에 포함되지 않음.'),
 'compare_etf_exposure':('partial','증권·회사 중복만 지원. 업종별 중복 계산은 아직 미지원.'),
 'get_previous_analyses':('partial','이전 해석과 도구 실행 ID를 보존. 과거 도구 근거를 그래프에서 해소하는 기능은 미완료.'),
 'get_flow_observations':('partial','장중 슬롯의 누적·구간 의미는 인증되지 않음.'),
 'get_security_classifications':('partial','시장가치 대상·통화·기준일 등 미확정 속성은 NULL로 보존.')}


if __name__=='__main__':
    with tempfile.TemporaryDirectory() as directory:
        provider=CQTools(lambda q,p:[],read_catalog(),directory,'2026-10-05T14:59:59+00:00')
        names=[s['function']['name'] for s in provider.schemas]
        if set(names)!=set(PURPOSES):raise ValueError('Purpose catalog and callable registry differ')
        result={'registered_count':len(names),'overall_status':'partial_support','tools':[
            {'name':n,'purpose':PURPOSES[n],'status':LIMITS.get(n,('implemented',None))[0],
             'limitation':LIMITS.get(n,('implemented',None))[1]} for n in names]}
    (APP/'data/cq-tool-capabilities.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'registered_count':len(names),'overall_status':result['overall_status']}))
