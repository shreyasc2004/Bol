"""Task-specific transliteration evaluation, not a pretrained benchmark claim."""
import argparse
import csv
import json
import time
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
from assistant_core import ServiceError, load_engine, model_label, transliterate


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def normalize(text):
    return unicodedata.normalize('NFC', text)


def run(dataset, output):
    cases = json.loads(Path(dataset).read_text(encoding='utf-8'))
    rows = []
    print('Loading Hindi model (model loading is excluded from case latency)...', flush=True)
    load_engine()
    for case in cases:
        started = time.perf_counter()
        try:
            prediction = transliterate(case['input'], case.get('preserve_english', False))['text']
            expected, actual = normalize(case['expected']), normalize(prediction)
            rows.append({**case, 'prediction': prediction, 'error': '',
                         'char_edits': distance(expected, actual), 'ref_chars': len(expected),
                         'word_edits': distance(expected.split(), actual.split()),
                         'ref_words': len(expected.split()), 'exact_match': expected == actual,
                         'latency_ms': round(1000 * (time.perf_counter() - started), 1)})
        except ServiceError as exc:
            rows.append({**case, 'prediction': '', 'error': str(exc), 'exact_match': False})
        print(f"Case {case['id']}/{len(cases)}: {'PASS' if rows[-1]['exact_match'] else 'REVIEW'}", flush=True)
    valid = [row for row in rows if not row['error']]
    metrics = {'engine': model_label(), 'dataset': str(dataset), 'cases': len(rows), 'completed': len(valid),
               'service_errors': len(rows) - len(valid),
               'exact_sentence_accuracy': sum(row['exact_match'] for row in rows) / max(1, len(rows)),
               'character_error_rate': sum(r['char_edits'] for r in valid) / max(1, sum(r['ref_chars'] for r in valid)) if valid else None,
               'word_error_rate': sum(r['word_edits'] for r in valid) / max(1, sum(r['ref_words'] for r in valid)) if valid else None,
               'mean_latency_ms': sum(r['latency_ms'] for r in valid) / len(valid) if valid else None,
               'notes': 'CER/WER and latency cover completed cases. Exact-match accuracy counts service errors as failures. Fixed evaluation sample, not a full benchmark score. See dataset attribution. NFC code-point CER.'}
    metrics['word_accuracy'] = max(0, 1 - metrics['word_error_rate']) if valid else None
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'evaluation.json').write_text(json.dumps({'metrics': metrics, 'cases': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    with (output / 'evaluation.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(dict.fromkeys(key for row in rows for key in row)))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(metrics, indent=2))
    return 1 if metrics['service_errors'] else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', default=str(Path(__file__).parent / 'data/evaluation.json'))
    parser.add_argument('--output', default=str(Path(__file__).parent / 'reports'))
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.dataset, args.output))
    except ServiceError as exc:
        parser.exit(1, str(exc) + '\n')
