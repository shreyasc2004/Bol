"""Create a small source ZIP and printable report. Requires Markdown for report rendering."""
import zipfile
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'submission'
OUT.mkdir(exist_ok=True)
report = (ROOT / 'docs/PROJECT.md').read_text(encoding='utf-8')
body = markdown.markdown(report, extensions=['tables', 'fenced_code'])
document = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Bol — Project Report</title>
<style>@page{size:A4;margin:17mm}body{font:12px/1.65 'Segoe UI','Nirmala UI',sans-serif;color:#253a35;max-width:800px;margin:30px auto}h1{font-size:27px;border-bottom:3px solid #c86736;padding-bottom:12px}h2{font-size:18px;margin-top:27px;break-after:avoid}table{border-collapse:collapse;width:100%;font-size:11px}td,th{border:1px solid #ccd4cc;padding:7px;text-align:left}th{background:#edf1e8}tr,pre{break-inside:avoid}pre{padding:12px;background:#f1f3ed;white-space:pre-wrap}a{color:#225c46}p{orphans:3;widows:3}@media print{body{margin:0}}</style>''' + body + '</html>'
(OUT / 'Bol_Project_Report.html').write_text(document, encoding='utf-8')
(OUT / 'Bol_Project_Report.md').write_text(report, encoding='utf-8')

roots = ['app.py', 'assistant_core.py', 'writing_backend.py', 'evaluate.py', 'evaluate_writing.py',
         'run.bat', 'requirements.txt', 'requirements-model.txt', '.env.example', '.gitignore', 'README.md',
         'static', 'templates', 'data', 'tests', 'docs', 'reports']
files = []
for name in roots:
    path = ROOT / name
    files.extend([path] if path.is_file() else [p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts])
files.extend(ROOT / 'scripts' / name for name in ['check_model.py', 'check_api.py', 'setup_sovereign.py', 'prepare_aksharantar.py', 'browser_check.py', 'package_submission.py'])
# Never write a credential to the archive, even if one was accidentally added to a tracked document.
env = ROOT / '.env'
key = ''
if env.exists():
    for line in env.read_text(encoding='utf-8').splitlines():
        if line.startswith('OPENROUTER_API_KEY='):
            key = line.split('=', 1)[1].strip()
for path in files:
    if key and key.encode() in path.read_bytes():
        raise RuntimeError('Credential found in source file: ' + str(path.relative_to(ROOT)))
    if re.search(rb'sk-or-v1-[a-f0-9]{64}', path.read_bytes()):
        raise RuntimeError('API credential found in source file: ' + str(path.relative_to(ROOT)))
archive = OUT / 'Bol_Hinglish_Assistant_Source.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(files):
        bundle.write(path, 'Bol_Hinglish_Assistant/' + path.relative_to(ROOT).as_posix())
    bundle.write(OUT / 'Bol_Project_Report.html', 'Bol_Hinglish_Assistant/docs/Printable_Report.html')
    if (OUT / 'Bol_Project_Report.pdf').exists():
        bundle.write(OUT / 'Bol_Project_Report.pdf', 'Bol_Hinglish_Assistant/docs/Project_Report.pdf')
print('Packaged', len(files), 'source/data/report files; credential scan passed.')
print('ZIP:', archive.name, '|', round(archive.stat().st_size / 1024), 'KB')
