"""Freeze the 13 canonical questions and Korean-equity scenarios before the full benchmark."""
import hashlib
import json
import re
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
SOURCE=Path('C:/Users/user/Documents/Obsidian Vault/Project/ETF ORCA/온톨로지 설계/공리와 목적 기반 CQ/02 목적 중심 역량질문.md')
CONTEXTS=[
    '대상은 PLUS K방산과 KODEX 방산이며 구성 기준일은 2026-10-02입니다. 다른 상품으로 임의 교체하지 마세요.',
    '대상은 PLUS K방산이며 관찰일은 2026-10-02입니다. 원화 약세·금리 상승이라는 전제부터 자료로 확인해 주세요. 전 거래일 비교가 필요하면 2026-10-01을 사용하세요.',
    '관심 기업은 한화에어로스페이스이며 2026년 9월 크로아티아 천무 수출 소식을 확인해 주세요.',
    '비교 기업은 한화에어로스페이스와 한화오션입니다. 2026년 2분기를 1분기와 비교하되 누적과 단일 분기를 혼동하지 마세요.',
    '대상은 PLUS K방산입니다. 2026-10-05 시점에서 향후 한 달을 판단하며, 구성은 2026-10-02 이하 최신 자료를 사용하세요.',
    '대상은 PLUS K방산이며 오늘은 2026-10-02로 고정합니다. 전 거래일은 2026-10-01입니다.',
    '대상은 PLUS K방산의 2026-10-02 보유 기업입니다. 2026년 9월에 공급자로 참여한 계약 체결 소식 중 계약 총액 1,000억 원 이상인 사례를 최대 세 개 확인해 주세요.',
    '대상은 PLUS K방산입니다. 2026-09-25까지 발행된 가장 최근 설명과 비교해, 2026-10-05까지 새로 확인된 사실을 조사하세요. 이전 설명이 없으면 그 한계를 구별하세요.',
    '대상은 PLUS K방산입니다. 2026-09-11 한화에어로스페이스의 크로아티아 수주 소식을 기준으로 당시 구성과 2026-10-02 구성을 비교하세요. 그 날짜 자료가 없으면 정확히 밝혀 주세요.',
    '대상은 PLUS K방산이며 2026-10-01 종가에서 2026-10-02 종가로의 움직임을 전체 보유 구성종목 기준으로 확인하세요. 조정 수익률과 관측 종가 변화를 구분하세요.',
    '대상은 PLUS K방산의 주요 보유 기업입니다. 2026년 9월 크로아티아 천무 수출 계획의 발표·계약·실행을 구분하고, 2026-10-05까지 확인된 진행을 설명하세요.',
    '한화에어로스페이스의 2026년 2분기 영업이익 발표를 확인하세요. 실제 발표 전에 알려진 같은 회계 범위·기간의 기대가 없으면 기대 초과 여부를 단정하지 마세요.',
    '대상은 PLUS K방산입니다. 수주 확대가 향후 한 달 전망을 지지한다는 가설을 점검하며, 2026-10-05까지 확인 가능한 반대 근거와 조사하지 못한 범위를 구별하세요.'
]
CHECKS=[
    ['동일 구성일','회사·분류 원비중 중복','미해소와 분류 기준'],
    ['같은 날짜 가격·NAV','수급 대상·단위·추정 구분','거시 전제 검증'],
    ['참여 역할','신규·변경·재보도 구분','원문과 후속 상태'],
    ['동일 기간·회계 범위','보고값과 계산값','판본·사업부문 한계'],
    ['실제 보유 노출','사건·재무·시장 근거','반대 근거·판단 변경 조건'],
    ['관측 가격과 구성종목','원인 후보와 인과 불확실성','이전 설명과 차이'],
    ['같은 사건의 공급 역할·금액','총액·통화·미확인 구분','세 사례 이내'],
    ['이전 설명의 기준시각','새로 확보된 정정 포함','기존 해석 변경 여부'],
    ['사건 당시 실제 구성','현재 구성','정확한 날짜 자료 부재'],
    ['전체 선택 집합','상승·하락·보합·미확인','원비중 유지'],
    ['발표와 실제 실행 구분','변경·취소 근거','동일성·최신 상태 한계'],
    ['발표 전 기대','동일 기간·회계 범위','비교 불가 또는 도구 계산'],
    ['주장을 약화하는 사실','조사 범위·자료 부재','판단을 바꿀 조건']
]


def prepare():
    raw=SOURCE.read_text(encoding='utf8');sections=re.split(r'^## CQ-',raw,flags=re.M)[1:]
    cases=[]
    for index,section in enumerate(sections):
        identifier=section[:2];question=re.search(r'^> (.+)$',section,re.M).group(1)
        cases.append({'id':'CQ'+identifier,'canonical_question':question,
            'question':CONTEXTS[index]+'\n\n'+question,'criteria':CHECKS[index]})
    assert len(cases)==13
    document={'version':1,'cutoff':'2026-10-05T14:59:59+00:00','question_source':SOURCE.name,
        'question_source_sha256':hashlib.sha256(raw.encode('utf8')).hexdigest(),'scope':'Korean equity theme ETFs',
        'grading':'Answer generation is not semantic success. Unsupported source data and failed intent checks remain separate.',
        'cases':cases}
    (APP/'data/cq-cases.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':prepare()
