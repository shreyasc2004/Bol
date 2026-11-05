"""One live local BharatGen writing request."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
from writing_backend import WritingError, configuration, generate_writing

print('Provider:', configuration()['label'], flush=True)
try:
    result = generate_writing('कृपया मुझे कल की बैठक का समय बताओ।', 'rewrite', 'formal')
    print('Result:', result['text'].encode('unicode_escape').decode('ascii'), flush=True)
    print('Actual model:', result['resolved_model'], flush=True)
except WritingError as exc:
    print(str(exc), flush=True)
    raise SystemExit(1)
