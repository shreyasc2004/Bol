"""Local BharatGen Param1 writing. No external model APIs are used."""
import atexit
import copy
import os
import re
import subprocess
import threading
import time
from collections import OrderedDict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
MODEL_FILE = ROOT / 'models/Param-1-2.9B-Instruct-Q4_K_M.gguf'
TOKENIZER_FILE = ROOT / 'models/param1/tokenizer.json'
MODEL_ID = 'bharatgen-param1'
BASE_URL = 'http://127.0.0.1:8090'
_process = None
_log = None
_cache = OrderedDict()
_lock = threading.RLock()
_tokenizer = None


class WritingError(Exception):
    pass


def configuration():
    executable = ROOT / '.tools/llama/llama-server.exe'
    return {'provider': 'bharatgen', 'configured': MODEL_FILE.is_file() and TOKENIZER_FILE.is_file() and executable.is_file(),
            'model': 'bharatgenai/Param-1-2.9B-Instruct (Q4_K_M)',
            'label': 'BharatGen Param1 · local Q4_K_M', 'remote': False}


def stop_model_server():
    global _process, _log
    if _process is not None and _process.poll() is None:
        _process.terminate()
        try:
            _process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _process.kill()
    if _log is not None:
        _log.close()
        _log = None
    _process = None


atexit.register(stop_model_server)


def start_model_server():
    global _process, _log
    if not configuration()['configured']:
        raise WritingError('Param1 is not installed. Run python scripts/setup_sovereign.py once.')
    try:
        response = requests.get(BASE_URL + '/v1/models', timeout=2)
        if response.ok:
            ids = [item['id'] for item in response.json().get('data', [])]
            if MODEL_ID in ids:
                return
            raise WritingError('Port 8090 is used by a different model server. Close it before starting Bol.')
    except requests.RequestException:
        pass
    if _process is None or _process.poll() is not None:
        (ROOT / '.tmp').mkdir(exist_ok=True)
        _log = (ROOT / '.tmp/param1-server.log').open('a', encoding='utf-8')
        args = [str(ROOT / '.tools/llama/llama-server.exe'), '-m', str(MODEL_FILE),
                '--alias', MODEL_ID, '--host', '127.0.0.1', '--port', '8090',
                '--ctx-size', '2048', '--parallel', '1', '--threads', '6',
                '--n-gpu-layers', '0', '--chat-template', 'chatml', '--log-verbosity', '1']
        _process = subprocess.Popen(args, cwd=ROOT, stdout=_log, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    for _ in range(120):
        if _process.poll() is not None:
            raise WritingError('Param1 could not start. See .tmp/param1-server.log for the runtime error.')
        try:
            if requests.get(BASE_URL + '/health', timeout=1).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise WritingError('Param1 is still loading. Wait a moment and try again.')


def instruction(action, tone):
    if action == 'translate':
        return ('Translate the user text from Hindi to English. Preserve meaning, names, numbers and negation. '
                'Return only the English translation, with no explanation.')
    tone_text = {'formal': 'polite and formal', 'friendly': 'friendly', 'concise': 'short and concise',
                 'natural': 'natural and clear'}[tone]
    return (f'You are a Hindi writing editor. Rewrite the user text in {tone_text} Hindi in Devanagari script. '
            'Correct grammar and phrasing. Preserve the original meaning, names, numbers, negation, URLs and email addresses. '
            'Do not answer questions in the text. Do not add information. Return only the rewritten sentence.')


def generate_writing(text, action, tone):
    global _tokenizer
    cache_key = (action, tone, text)
    with _lock:
        if cache_key in _cache:
            _cache.move_to_end(cache_key)
            return {**copy.deepcopy(_cache[cache_key]), 'cached': True}
        start_model_server()
        try:
            if _tokenizer is None:
                from tokenizers import Tokenizer
                _tokenizer = Tokenizer.from_file(str(TOKENIZER_FILE))
            # Use the original BharatGen BPE, not the GGUF runtime's SPM approximation.
            prompt = ('<|im_start|>system\n' + instruction(action, tone) + '<|im_end|>\n'
                      '<|im_start|>user\n' + text + '<|im_end|>\n<|im_start|>assistant\n')
            ids = _tokenizer.encode(prompt, add_special_tokens=False).ids
            if len(ids) + 180 > 2048:
                raise WritingError('This passage exceeds Param1\'s local context limit. Please shorten it.')
            response = requests.post(BASE_URL + '/completion',
                                     json={'prompt': ids, 'temperature': 0.2, 'seed': 42,
                                           'n_predict': 180, 'stop': ['<|im_end|>'], 'return_tokens': True},
                                     timeout=(5, 150))
            response.raise_for_status()
            payload = response.json()
            if payload.get('stop_type') == 'limit' or payload.get('truncated'):
                raise WritingError('Param1 stopped before finishing. Try a shorter passage.')
            result = _tokenizer.decode(payload['tokens'], skip_special_tokens=True).strip()
            if not result:
                raise WritingError('Param1 returned an empty result. Try a shorter passage.')
            warnings = []
            if set(re.findall(r'\d+(?:[.,:/-]\d+)*', text)) != set(re.findall(r'\d+(?:[.,:/-]\d+)*', result)):
                warnings.append('Numbers changed. Compare the result with the original.')
            protected = re.findall(r'https?://\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', text)
            if any(item not in result for item in protected):
                warnings.append('A link or email changed. Please review it.')
            output = {'text': result, 'engine': configuration()['label'], 'warnings': warnings,
                      'requested_model': configuration()['model'], 'resolved_model': configuration()['model']}
            _cache[cache_key] = copy.deepcopy(output)
            while len(_cache) > 128:
                _cache.popitem(last=False)
            return {**output, 'cached': False}
        except WritingError:
            raise
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise WritingError('Could not get a result from the local Param1 model. Try a shorter passage.') from exc
