"""Create a fixed, attributed 50-word Hindi test sample before inference."""
import json
import random
import re
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with zipfile.ZipFile(ROOT / 'models/aksharantar-hin.zip') as bundle:
    with bundle.open('hin_test.json') as file:
        rows = [json.loads(line) for line in file if line.strip()]
eligible = [row for row in rows if re.fullmatch('[A-Za-z]{2,30}', row['english word'])]
sample = random.Random(3235).sample(eligible, 50)
cases = [{'id': row['unique_identifier'], 'category': row['source'],
          'input': row['english word'], 'expected': row['native word'], 'preserve_english': False,
          'dataset': 'ai4bharat/Aksharantar', 'split': 'hin_test'} for row in sample]
(ROOT / 'data/aksharantar_sample.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
print('Prepared 50 official Hindi test pairs; seed=3235; selected before inference.')
print('Groups:', dict(Counter(row['category'] for row in cases)))
