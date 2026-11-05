"""Download/load the model once and verify live inference."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from assistant_core import load_engine, transliterate

load_engine()
result = transliterate('namaste, aap kaise hain?')
print(result['text'].encode('unicode_escape').decode('ascii'))
print('Engine:', result['engine'])
