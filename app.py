import os
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

load_dotenv()
from assistant_core import ServiceError, cleanup, generate, model_label, transliterate
from writing_backend import configuration

app = Flask(__name__)
app.config.update(MAX_CONTENT_LENGTH=24_000)
app.json.ensure_ascii = False


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/api/status')
def status():
    writing = configuration()
    return jsonify(transliteration_engine=model_label(), llm_configured=writing['configured'],
                   llm_model=writing['model'], writing_provider=writing['provider'],
                   writing_label=writing['label'], writing_remote=writing['remote'], max_characters=2000)


@app.post('/api/write')
def write():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Send a JSON object.'), 400
    text = data.get('text')
    if not isinstance(text, str) or not text.strip():
        return jsonify(error='Type some text first.'), 400
    if len(text) > 2000:
        return jsonify(error='Please use 2,000 characters or fewer.'), 400
    action = data.get('action', 'convert')
    if not isinstance(action, str) or action not in {'convert', 'cleanup', 'rewrite', 'translate'}:
        return jsonify(error='Unknown writing action.'), 400
    tone = data.get('tone', 'natural')
    if not isinstance(tone, str) or tone not in {'natural', 'formal', 'friendly', 'concise'}:
        return jsonify(error='Choose a valid tone.'), 400
    preserve = data.get('preserve_english', True)
    if not isinstance(preserve, bool):
        return jsonify(error='preserve_english must be true or false.'), 400
    started = time.perf_counter()
    try:
        if action == 'convert':
            result = transliterate(text, preserve)
        elif action == 'cleanup':
            result = {'text': cleanup(text), 'engine': 'Basic punctuation and spacing cleanup'}
        else:
            result = generate(text, action, tone)
        result['elapsed_ms'] = round((time.perf_counter() - started) * 1000)
        return jsonify(result)
    except ServiceError as exc:
        return jsonify(error=str(exc)), 503


@app.errorhandler(HTTPException)
def http_error(exc):
    return jsonify(error=exc.description), exc.code


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5050')), debug=False)
