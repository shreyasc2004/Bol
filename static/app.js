const $ = id => document.getElementById(id);
let busy = false, alternatives = [], llmReady = false;
const buttons = ['convert', 'cleanup', 'rewrite', 'translate', 'clear', 'copy', 'download'];
function controls() {
  buttons.forEach(id => { $(id).disabled = busy || (['rewrite', 'translate'].includes(id) && !llmReady) || (['copy', 'download'].includes(id) && !$('output').value); });
  document.querySelectorAll('[data-example]').forEach(b => b.disabled = busy);
  $('source').disabled = busy; $('output').disabled = busy; $('preserve').disabled = busy;
  $('convert').textContent = busy ? 'Working…' : 'Convert to Hindi ↗';
  $('output').setAttribute('aria-busy', String(busy));
  document.body.classList.toggle('busy', busy);
}
function message(text, success = false) { $('message').textContent = text; $('message').classList.toggle('success', success); $('message').hidden = !text; }
function count() { $('count').textContent = `${$('source').value.length.toLocaleString()} / 2,000`; }
function resetResult() { $('output').value = ''; alternatives = []; $('suggestions').hidden = true; $('result-label').textContent = 'Ready when you are'; $('result-meta').textContent = 'Your converted text will appear here.'; message(''); controls(); }
$('source').addEventListener('input', () => { count(); resetResult(); });
$('preserve').addEventListener('change', resetResult);
$('clear').onclick = () => { $('source').value = ''; count(); resetResult(); $('source').focus(); };
document.querySelectorAll('[data-example]').forEach(button => button.onclick = () => { $('source').value = button.dataset.example; count(); resetResult(); $('source').focus(); });
$('output').addEventListener('input', () => { alternatives = []; $('suggestions').hidden = true; $('result-label').textContent = 'Edited by you'; controls(); });
function showWords() {
  $('word-options').replaceChildren(); $('candidate-options').replaceChildren();
  $('suggestions').hidden = alternatives.length === 0;
  alternatives.forEach((word, index) => {
    const button = document.createElement('button'); button.textContent = word.selected; button.type = 'button'; button.setAttribute('aria-pressed', 'false');
    button.onclick = () => {
      document.querySelectorAll('#word-options button').forEach(b => b.setAttribute('aria-pressed', 'false')); button.setAttribute('aria-pressed', 'true');
      $('candidate-options').replaceChildren(document.createTextNode(`${word.source} → `));
      word.candidates.forEach(candidate => {
        const option = document.createElement('button'); option.textContent = candidate; option.lang = 'hi';
        option.onclick = () => {
          const chars = Array.from($('output').value), delta = Array.from(candidate).length - (word.end - word.start);
          $('output').value = chars.slice(0, word.start).join('') + candidate + chars.slice(word.end).join('');
          word.end += delta; word.selected = candidate;
          alternatives.slice(index + 1).forEach(next => { next.start += delta; next.end += delta; });
          button.textContent = candidate; $('result-label').textContent = 'Spelling updated';
        };
        $('candidate-options').append(option);
      });
    };
    $('word-options').append(button);
  });
}
async function write(action) {
  if (busy) return;
  const text = action === 'convert' ? $('source').value : ($('output').value || $('source').value);
  if (!text.trim()) { message('Type some Hinglish or try an example first.'); $('source').focus(); return; }
  if (text.length > 2000) { message('Please use 2,000 characters or fewer.'); return; }
  busy = true; controls(); message(action === 'convert' ? 'Converting your words. The first request also loads the Hindi model.' : 'Working on your text…', true);
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 180000);
  try {
    const response = await fetch('/api/write', { method: 'POST', headers: {'Content-Type': 'application/json'}, signal: controller.signal,
      body: JSON.stringify({ text, action, tone: $('tone').value, preserve_english: $('preserve').checked }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Something went wrong. Please retry.');
    $('output').value = data.text; $('output').lang = action === 'translate' ? 'en' : 'hi';
    $('result-label').textContent = action === 'convert' ? 'Converted · editable' : action === 'translate' ? 'English · editable' : 'Updated · editable';
    $('result-meta').textContent = `${data.engine} · ${(data.elapsed_ms / 1000).toFixed(1)}s`;
    alternatives = data.alternatives || []; showWords(); message((data.warnings || []).join(' '));
    if (data.cached) $('result-meta').textContent += ' · saved request';
  } catch (error) { message(error.name === 'AbortError' ? 'This took too long. Check the model server and retry.' : error.message); }
  finally { clearTimeout(timer); busy = false; controls(); }
}
['convert', 'cleanup', 'rewrite', 'translate'].forEach(action => $(action).onclick = () => write(action));
$('source').addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); write('convert'); } });
$('copy').onclick = async () => { try { await navigator.clipboard.writeText($('output').value); message('Copied to clipboard.', true); } catch { $('output').focus(); $('output').select(); message('Select and copy the output with Ctrl+C.'); } };
$('download').onclick = () => { const url = URL.createObjectURL(new Blob(['\ufeff' + $('output').value], {type: 'text/plain;charset=utf-8'})); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'bol-writing.txt'; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); };
fetch('/api/status').then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(data => {
  llmReady = data.llm_configured;
  $('llm-note').textContent = llmReady ? `${data.writing_label}. Your first AI request loads the model; please allow a moment.` : 'Install BharatGen Param1 using the setup instructions to enable AI writing.';
  $('engine-note').textContent = `Transliteration engine: ${data.transliteration_engine}. Model availability is checked on the first conversion.`;
  controls();
}).catch(() => { $('llm-note').textContent = 'Could not connect to the app. Restart the Python server and refresh.'; });
count(); controls();
