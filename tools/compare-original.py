"""Compare captured source and packaged frames; never update the source baseline."""
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

root = Path('artifacts/original-fidelity')
if not json.loads((root / 'run.json').read_text(encoding='utf-8'))['complete']:
    raise SystemExit('Capture did not finish; do not compare a mixture of old and new frames')
frames = json.loads((root / 'frames.json').read_text(encoding='utf-8'))
labels = [f"{frame['label']}-{time}.png" for frame in frames
          if frame['name'] == 'source' for time in frame['times']]

def compare(label, target):
    source = root / f'source-{label}'
    actual = root / f'{target}-{label}'
    a, b = Image.open(source).convert('RGB'), Image.open(actual).convert('RGB')
    if a.size != b.size:
        raise ValueError(f'{label}: viewport mismatch')
    difference = ImageChops.difference(a,b)
    channels = difference.split()
    maximum = ImageChops.lighter(ImageChops.lighter(*channels[:2]),channels[2])
    count = maximum.histogram()
    row = {'frame':label,'differentPixels':sum(count[1:]),'pixelsOver20':sum(count[21:]),'meanChannelDifference':round(sum(ImageStat.Stat(difference).mean)/3,6)}
    if row['differentPixels']:
        difference.save(root / f'diff-{target}-{label}')
    return row

if not labels:
    raise SystemExit('No captured source frames')
packaged_differences = 0
for target in ['packaged', 'source-repeat']:
    if not any(frame['name'] == target for frame in frames):
        continue
    rows = [compare(label, target) for label in labels]
    filename = 'pixels.json' if target == 'packaged' else 'pixels-source-repeat.json'
    (root / filename).write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps({'target':target,'frames':len(rows),'exact':sum(r['differentPixels']==0 for r in rows),'differences':[r for r in rows if r['differentPixels']]}))
    if target == 'packaged':
        packaged_differences = sum(r['differentPixels'] != 0 for r in rows)
if packaged_differences:
    raise SystemExit(f'{packaged_differences} packaged frame(s) differ; pixel equality has not passed')
