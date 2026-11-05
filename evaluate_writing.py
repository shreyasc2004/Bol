"""Task-specific evaluation of the local BharatGen Param1 writer."""
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')
from writing_backend import WritingError, configuration, generate_writing

ROOT = Path(__file__).parent


def character_fscore(reference, prediction):
    """Mean character 1–6 gram F2; diagnostic lexical overlap, not semantic quality."""
    a, b = ''.join(reference.split()).lower(), ''.join(prediction.split()).lower()
    scores = []
    for n in range(1, min(6, len(a), len(b)) + 1):
        ca = Counter(a[i:i+n] for i in range(len(a) - n + 1))
        cb = Counter(b[i:i+n] for i in range(len(b) - n + 1))
        overlap = sum((ca & cb).values())
        precision, recall = overlap / sum(cb.values()), overlap / sum(ca.values())
        scores.append(5 * precision * recall / (4 * precision + recall) if precision + recall else 0)
    return sum(scores) / len(scores) if scores else 0


def main():
    config = configuration()
    cases = json.loads((ROOT / 'data/writing_evaluation.json').read_text(encoding='utf-8'))
    report = {'date_utc': datetime.now(timezone.utc).isoformat(), 'requested_model': config['model'],
              'provider': config['provider'], 'status': 'pending', 'cases': [],
              'notes': 'Authored pilot. Character n-gram F2 is lexical overlap only, not a human fluency or meaning score. References require Hindi review.'}
    if not config['configured']:
        report['reason'] = 'Local Param1 model has not been installed.'
    else:
        for case in cases:
            started = time.perf_counter()
            try:
                result = generate_writing(case['input'], case['action'], case['tone'])
                report['cases'].append({**case, 'prediction': result['text'], 'resolved_model': result['resolved_model'],
                                        'warnings': result['warnings'], 'latency_ms': round(1000 * (time.perf_counter() - started)),
                                        'character_ngram_f2': character_fscore(case['reference'], result['text']),
                                        'numbers_preserved': set(re.findall(r'\d+', case['input'])) == set(re.findall(r'\d+', result['text']))})
                print(case['id'] + ' completed', flush=True)
            except WritingError as exc:
                report['reason'] = str(exc)
                break
        if len(report['cases']) == len(cases):
            report['status'] = 'completed'
            report['metrics'] = {'cases': len(cases),
                                 'number_preservation_rate': sum(row['numbers_preserved'] for row in report['cases']) / len(cases),
                                 'mean_character_ngram_f2': sum(row['character_ngram_f2'] for row in report['cases']) / len(cases),
                                 'mean_latency_ms': sum(row['latency_ms'] for row in report['cases']) / len(cases)}
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports/writing_evaluation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Writing evaluation:', report['status'], report.get('reason', ''), flush=True)
    return 0 if report['status'] == 'completed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
