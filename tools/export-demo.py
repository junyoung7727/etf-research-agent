"""Export the same key-free fixtures for the offline app and public demo."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server.data import AS_OF, demo_detail, demo_instruments

items = demo_instruments()
data = {'catalog': {'instruments': items, 'dataMode': 'DEMO', 'asOf': AS_OF,
                    'feedState': 'DEMO', 'analysisEnabled': False},
        'details': {item['id']: demo_detail(item) for item in items}}
(ROOT / 'public/demo-api.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
print('Exported six explicitly labelled demo ETFs; no provider calls.')
