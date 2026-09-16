"""Explicit design fixtures. No value in this module is a live market assertion."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

AS_OF = '2026-09-04T15:30:00+09:00'
CATALOG = [
    ('396500', 'TIGER 반도체TOP10', '반도체TOP10', 'AI·반도체', '#4431e9', 12806, 12445),
    ('449450', 'PLUS K방산', 'K방산', '방산', '#191f28', 21416, 21037),
    ('487230', 'KODEX 미국AI전력핵심인프라', '미국AI전력', '배당·인프라', '#089376', 15366, 15229),
    ('439870', 'KODEX 국고채30년액티브', '국고채30년', '채권', '#ed6534', 97420, 97032),
    ('364970', 'TIGER 바이오TOP10', '바이오TOP10', '바이오', '#913eea', 8150, 8150),
    ('377990', 'TIGER Fn신재생에너지', 'Fn신재생에너지', '친환경', '#e8a438', 6520, 6650),
]


def number(value, *, absolute=False):
    if value is None or str(value).strip() == '':
        return None
    try:
        result = Decimal(str(value).replace(',', ''))
        if not result.is_finite():
            return None
        return abs(result) if absolute else result
    except InvalidOperation:
        return None


def ratio(price, previous):
    return None if price is None or previous is None or previous <= 0 else price / previous - 1


def decimal_text(value):
    return None if value is None else format(value, 'f')


def demo_instruments():
    return [{
        'id': symbol, 'name': name, 'shortName': short, 'theme': theme,
        'color': color, 'icon': i, 'currency': 'KRW',
        'quote': {'price': str(price), 'previousClose': str(previous),
                  'changeRatio': decimal_text(ratio(Decimal(price), Decimal(previous))),
                  'asOf': AS_OF, 'receivedAt': AS_OF, 'status': 'READY',
                  'snapshotId': f'demo-v1:{symbol}', 'feedState': 'DEMO'},
    } for i, (symbol, name, short, theme, color, price, previous) in enumerate(CATALOG)]


def demo_candles(instrument):
    # A reproducible artificial curve, pinned to the quote's previous/current closes.
    days, current = [], date(2026, 9, 4)
    while len(days) < 65:
        if current.weekday() < 5:
            days.append(current)
        current -= timedelta(days=1)
    days.reverse()
    price = int(instrument['quote']['price'])
    closes = [round(price * (0.89 + i * 0.00165 + (((i * 17) % 13) - 6) * 0.006)) for i in range(65)]
    closes[-2:] = [int(instrument['quote']['previousClose']), price]
    return [{'date': day.isoformat(), 'open': str(closes[max(0, i-1)]),
             'close': str(close), 'high': str(max(closes[max(0, i-1)], close) + 90),
             'low': str(min(closes[max(0, i-1)], close) - 70), 'volume': 210000 + i * 3100,
             'isComplete': True} for i, (day, close) in enumerate(zip(days, closes))]


def factors(candles):
    completed = [number(c['close'], absolute=True) for c in candles if c['isComplete']]
    completed = [c for c in completed if c is not None]
    ma20 = sum(completed[-20:]) / 20 if len(completed) >= 20 else None
    r20 = ratio(completed[-1], completed[-21]) if len(completed) >= 21 else None
    return [{
        'kind': key, 'label': label, 'status': 'READY' if key == 'chart' and ma20 is not None else 'MISSING',
        'explanation': explanation,
        'metrics': ([{'label': '20일 이동평균', 'value': decimal_text(ma20), 'unit': '원'},
                     {'label': '20거래일 수익률', 'value': decimal_text(r20 * 100 if r20 is not None else None), 'unit': '%'}]
                    if key == 'chart' else [{'label': label + ' 근거 자료', 'value': None, 'unit': ''}]),
    } for key, label, explanation in [
        ('issue', '이슈', '기사의 원문·발행 시각과 ETF의 연관성을 함께 확인해요.'),
        ('chart', '차트', '완료된 일봉으로 계산해요. 이동평균과 과거 수익률은 미래 수익을 보장하지 않아요.'),
        ('macro', '매크로', '금리·환율의 기준 시점과 편입 자산에 미치는 경로를 확인해요.'),
        ('value', '밸류', '자산군에 맞는 평가 지표를 사용해요. 채권 ETF에 주식 PER을 적용하지 않아요.'),
        ('flow', '수급', '투자자별 매매의 단위와 집계 기간이 확인된 자료가 필요해요.'),
    ]]


def demo_detail(instrument):
    candles = demo_candles(instrument)
    holdings = ([
        {'name': 'SK하이닉스', 'weight': 0.3694, 'dayReturn': 0.034, 'return20': 0.098, 'theme': 'AI·반도체'},
        {'name': '삼성전자', 'weight': 0.2314, 'dayReturn': 0.028, 'return20': 0.109, 'theme': 'AI·반도체'},
        {'name': '한미반도체', 'weight': 0.0689, 'dayReturn': 0.012, 'return20': 0.146, 'theme': 'AI·반도체'},
        {'name': '주성엔지니어링', 'weight': 0.0361, 'dayReturn': -0.006, 'return20': 0.052, 'theme': 'AI·반도체'},
        {'name': '이오테크닉스', 'weight': 0.0241, 'dayReturn': 0.008, 'return20': 0.032, 'theme': 'AI·반도체'},
    ] if instrument['id'] == '396500' else [])
    source = {'id': 'demo-method', 'title': '화면 검수용 예시 자료', 'publisher': 'EDGE 데모', 'url': None,
              'publishedAt': AS_OF, 'excerpt': '실제 기사·공시가 아닙니다. 시세, 구성비와 설명은 화면 동작을 확인하기 위한 예시입니다.'}
    analyses = []
    for offset in (0, 1, 2):
        subset = candles[:len(candles)-offset] if offset else candles
        day = subset[-1]['date']
        analyses.append({'id': f'demo-v1:{instrument["id"]}:{day}', 'asOf': day+'T15:30:00+09:00',
                         'headline': f'{instrument["shortName"]}, 움직임 뒤의 근거를 살펴봐요',
                         'summary': '가격의 변화, ETF의 구성, 자료의 기준일을 함께 확인해요. 지금 보고 있는 내용은 예시이며 전망 판단은 보류 중이에요.',
                         'factors': factors(subset), 'sources': [source], 'dataMode': 'DEMO', 'outlook': None,
                         'changeReason': '각 날짜에 고정한 예시 일봉으로 계산했어요. 실제 과거 AI 분석 이력이 아니에요.',
                         'modelId': 'demo-fixture-v1'})
    return {'instrument': instrument, 'candles': candles, 'holdings': holdings,
            'holdingsAsOf': '2026-09-04' if holdings else None,
            'residualWeight': round(1 - sum(h['weight'] for h in holdings), 6),
            'holdingsStatus': 'READY' if holdings else 'MISSING',
            'fundamentals': [{'label': label, 'value': None} for label in ['총보수 (연)', '분배율 (연)', '순자산', '추적오차']],
            'analyses': analyses, 'dataMode': 'DEMO'}
