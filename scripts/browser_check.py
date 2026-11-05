"""Optional local browser QA using an isolated Edge debugging instance (port 9223).

Requires the developer-only websockets package; not used by the application.
"""
import base64
import json
from pathlib import Path

import requests
from websockets.sync.client import connect

pages = requests.get('http://127.0.0.1:9223/json/list', timeout=5).json()
page = next(page for page in pages if page['type'] == 'page' and '127.0.0.1:5050' in page['url'])
sequence = 0
with connect(page['webSocketDebuggerUrl'], open_timeout=5, max_size=8_000_000) as socket:
    def cdp(method, params=None):
        global sequence
        sequence += 1
        socket.send(json.dumps({'id': sequence, 'method': method, 'params': params or {}}))
        while True:
            reply = json.loads(socket.recv(timeout=45))
            if reply.get('id') == sequence:
                if 'error' in reply:
                    raise RuntimeError(reply['error'])
                return reply.get('result', {})

    def js(expression):
        result = cdp('Runtime.evaluate', {'expression': expression, 'awaitPromise': True, 'returnByValue': True})
        if 'exceptionDetails' in result:
            raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')

    cdp('Emulation.setDeviceMetricsOverride', {'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
    status = requests.get('http://127.0.0.1:5050/api/status', timeout=5).json()
    assert js('document.getElementById("rewrite").disabled') == (not status['llm_configured'])
    assert 'sk-or-' not in js('document.documentElement.outerHTML'), 'Credential must never be in HTML'
    result = js('''(async () => {
      const input = document.getElementById('source');
      input.value = '😊 mujhe kal college jana hai';
      input.dispatchEvent(new Event('input', {bubbles:true}));
      document.getElementById('convert').click();
      const started = Date.now();
      while(document.getElementById('convert').disabled && Date.now() - started < 35000)
        await new Promise(resolve => setTimeout(resolve, 100));
      return {output:document.getElementById('output').value,
              message:document.getElementById('message').textContent,
              alternatives:document.querySelectorAll('#word-options button').length};
    })()''')
    assert result['output'] == '😊 मुझे कल college जाना है', result
    assert result['alternatives'] == 4, result
    js("document.querySelector('#word-options button').click()")
    chosen = js("document.querySelectorAll('#candidate-options button')[1].textContent")
    js("document.querySelectorAll('#candidate-options button')[1].click()")
    changed = js('document.getElementById("output").value')
    assert changed == '😊 ' + chosen + ' कल college जाना है', ascii(changed)
    output = Path(__file__).resolve().parents[1] / '.tmp'
    output.mkdir(exist_ok=True)
    image = cdp('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
    (output / 'bol-desktop.png').write_bytes(base64.b64decode(image['data']))
    cdp('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
    js('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    assert js('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile horizontal overflow'
    image = cdp('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
    (output / 'bol-mobile.png').write_bytes(base64.b64decode(image['data']))
    js('document.getElementById("clear").click()')
    assert js('document.getElementById("output").value') == ''
    assert js('document.getElementById("copy").disabled')
    if status['llm_configured']:
        rewritten = js('''(async () => {
          const input = document.getElementById('source');
          input.value = 'मैं यह कहना चाहता हूँ कि मैं कल नहीं आ पाऊँगा।';
          input.dispatchEvent(new Event('input', {bubbles:true}));
          document.getElementById('tone').value = 'concise';
          document.getElementById('rewrite').click();
          const start = Date.now();
          while(document.getElementById('rewrite').disabled && Date.now() - start < 40000)
            await new Promise(resolve => setTimeout(resolve, 100));
          return {text:document.getElementById('output').value, model:document.getElementById('result-meta').textContent};
        })()''')
        assert 'नहीं' in rewritten['text'] and len(rewritten['text']) < 44, rewritten
        assert 'BharatGen' in rewritten['model'], rewritten
        translated = js('''(async () => {
          document.getElementById('translate').click();
          const start = Date.now();
          while(document.getElementById('translate').disabled && Date.now() - start < 40000)
            await new Promise(resolve => setTimeout(resolve, 100));
          return document.getElementById('output').value;
        })()''')
        assert 'tomorrow' in translated.lower(), translated
        assert 'not' in translated.lower() or "won't" in translated.lower(), translated
    print('Browser checks passed: conversion, spelling replacement, clear, desktop/mobile layout, live BharatGen phrasing and translation.')
    cdp('Browser.close')
