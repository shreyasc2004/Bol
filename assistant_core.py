"""Hindi transliteration and optional local generative writing assistance."""
import os
import re
import threading
from functools import lru_cache

from writing_backend import WritingError, generate_writing


class ServiceError(Exception):
    pass


TOKEN = re.compile(r"https?://[^\s]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|[A-Za-z]+|[^A-Za-z]+")
# Explicit, limited policy; not automatic English language identification.
ENGLISH_WORDS = frozenset("college project assignment meeting email online class exam laptop deadline presentation report file download upload website app python code github pdf ai api wifi zoom teams link office sir madam please thanks thank you hello hi good morning evening night happy birthday".split())
_model = None
_lock = threading.RLock()
_model_label = None


def model_label():
    kind = os.getenv('XLIT_MODEL_TYPE', 'rnn')
    return 'AI4Bharat Hindi RNN v0.5' if kind == 'rnn' else 'AI4Bharat IndicXlit transformer'


def load_engine():
    global _model, _model_label
    with _lock:
        if _model is None:
            kind = os.getenv('XLIT_MODEL_TYPE', 'rnn')
            if kind not in {'rnn', 'transformer'}:
                raise ServiceError('XLIT_MODEL_TYPE must be rnn or transformer.')
            try:
                import torch
                from ai4bharat.transliteration import XlitEngine
                torch.set_num_threads(2)
                engine = XlitEngine('hi', beam_width=int(os.getenv('XLIT_BEAM_WIDTH', '4')),
                                    rescore=True, model_type=kind)
                probe = engine.translit_word('namaste', lang_code='hi', topk=1)
                if not isinstance(probe, list) or not probe:
                    raise ValueError('Hindi checkpoint did not load')
                _model = engine
                _model_label = model_label()
            except (Exception, SystemExit) as exc:
                raise ServiceError('Hindi model could not load. Run the model setup in README.md. '
                                   'The first start needs internet to download the checkpoint.') from exc
        return _model


@lru_cache(maxsize=4096)
def word_candidates(word):
    with _lock:
        result = load_engine().translit_word(word.lower(), lang_code='hi', topk=4)
    if not isinstance(result, list) or not result or not all(isinstance(x, str) and x for x in result):
        raise ServiceError('The Hindi model returned an invalid prediction. Please try a shorter word.')
    return tuple(result)


def transliterate(text, preserve_english=True):
    """Preserve original whitespace, native script, URLs, punctuation and numbers."""
    output, alternatives = [], []
    for match in TOKEN.finditer(text):
        token = match.group()
        if not re.fullmatch('[A-Za-z]+', token):
            output.append(token)
            continue
        if preserve_english and (token.lower() in ENGLISH_WORDS or (token.isupper() and len(token) > 1)):
            output.append(token)
            continue
        if len(token) > 50:
            raise ServiceError('Please keep individual Roman-script words under 51 letters.')
        candidates = word_candidates(token)
        start = sum(len(part) for part in output)
        output.append(candidates[0])
        alternatives.append({'source': token, 'selected': candidates[0],
                             'candidates': candidates, 'start': start, 'end': start + len(candidates[0])})
    return {'text': ''.join(output), 'alternatives': alternatives, 'engine': _model_label or model_label()}


def cleanup(text):
    """Deterministic punctuation cleanup; deliberately not described as an LLM."""
    text = re.sub(r'[ \t]+', ' ', text.strip())
    text = re.sub(r' +([,!?।])', r'\1', text)
    return text


def generate(text, action, tone):
    try:
        return generate_writing(text, action, tone)
    except WritingError as exc:
        raise ServiceError(str(exc)) from exc
