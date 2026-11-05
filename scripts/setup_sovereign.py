"""Fetch Param1's compact GGUF, a CPU runtime, and official Aksharantar data."""
import hashlib
import json
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REVISION = '36bfaad11e8c494d982517f48e004de641def42f'
GGUF = 'Param-1-2.9B-Instruct-Q4_K_M.gguf'
REPO = 'arunmcops/Param-1-2.9B-Instruct-GGUF'
DATA_REV = 'e418c1fc928d9f5393af33268472cf20c1891be8'
RUNTIME_TAG = 'b12034'
ORIGINAL_REVISION = 'f9b32a727458727ff515fea5d82df00ae9b7ad56'


def get_json(url):
    response = requests.get(url, timeout=40)
    response.raise_for_status()
    return response.json()


def fetch(url, target, expected=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print('Present:', target.name, flush=True)
    else:
        with requests.get(url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=(30, 90)) as response:
            response.raise_for_status()
            ranged = response.status_code == 206
            total = int(response.headers['content-range'].split('/')[-1]) if ranged else int(response.headers.get('content-length', 0))
        if ranged and total > 80_000_000:
            parts = target.with_suffix(target.suffix + '.parts')
            parts.mkdir(exist_ok=True)
            size = 32 * 1024 * 1024
            ranges = [(start, min(start + size - 1, total - 1)) for start in range(0, total, size)]

            def segment(bounds):
                start, end = bounds
                path = parts / str(start)
                required = end - start + 1
                for attempt in range(4):
                    offset = path.stat().st_size if path.exists() else 0
                    if offset == required:
                        return path
                    try:
                        with requests.get(url + f'?download=true&offset={start + offset}',
                                          headers={'Range': f'bytes={start + offset}-{end}'},
                                          stream=True, timeout=(30, 120)) as response:
                            response.raise_for_status()
                            if response.headers.get('content-range') != f'bytes {start + offset}-{end}/{total}':
                                raise OSError('Unexpected range')
                            with path.open('ab') as file:
                                for chunk in response.iter_content(1024 * 1024):
                                    file.write(chunk)
                        if path.stat().st_size != required:
                            raise OSError('Incomplete download')
                        print(f'{target.name}: {start // 1_000_000}-{end // 1_000_000} MB complete', flush=True)
                        return path
                    except (requests.RequestException, OSError):
                        if attempt == 3:
                            raise
            with ThreadPoolExecutor(max_workers=8) as pool:
                segments = list(pool.map(segment, ranges))
            temporary = target.with_suffix(target.suffix + '.part')
            with temporary.open('wb') as file:
                for part in segments:
                    with part.open('rb') as source:
                        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
                            file.write(chunk)
            temporary.replace(target)
        else:
            temporary = target.with_suffix(target.suffix + '.part')
            with requests.get(url, stream=True, timeout=(30, 120)) as response:
                response.raise_for_status()
                with temporary.open('wb') as file:
                    for chunk in response.iter_content(1024 * 1024):
                        file.write(chunk)
            temporary.replace(target)
        print('Downloaded:', target.name, flush=True)
    digest = hashlib.sha256()
    with target.open('rb') as file:
        for chunk in iter(lambda: file.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    actual = digest.hexdigest()
    if expected and actual != expected.removeprefix('sha256:'):
        raise ValueError('SHA-256 mismatch: ' + target.name)
    return actual


def extract(archive, target):
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            if not (target / item.filename).resolve().is_relative_to(target.resolve()):
                raise ValueError('Unsafe archive path')
        for item in bundle.infolist():
            path = target / item.filename
            if item.is_dir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            if path.exists() and path.stat().st_size == item.file_size:
                checksum = 0
                with path.open('rb') as file:
                    for chunk in iter(lambda: file.read(1024 * 1024), b''):
                        checksum = zlib.crc32(chunk, checksum)
                if checksum == item.CRC:
                    continue
            bundle.extract(item, target)


def main():
    files = get_json(f'https://huggingface.co/api/models/{REPO}/tree/{REVISION}')
    record = next(item for item in files if item['path'] == GGUF)
    release = get_json(f'https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{RUNTIME_TAG}')
    runtime = next(item for item in release['assets'] if item['name'].endswith('bin-win-cpu-x64.zip'))
    original_files = get_json(f'https://huggingface.co/api/models/bharatgenai/Param-1-2.9B-Instruct/tree/{ORIGINAL_REVISION}')
    tokenizer = next(item for item in original_files if item['path'] == 'tokenizer.json')
    jobs = [
        (f'https://huggingface.co/{REPO}/resolve/{REVISION}/{GGUF}', ROOT / 'models' / GGUF, record['lfs']['oid']),
        (runtime['browser_download_url'], ROOT / 'models/llama-cpu.zip', runtime.get('digest')),
        (f'https://huggingface.co/datasets/ai4bharat/Aksharantar/resolve/{DATA_REV}/hin.zip', ROOT / 'models/aksharantar-hin.zip', None),
        (f'https://huggingface.co/bharatgenai/Param-1-2.9B-Instruct/resolve/{ORIGINAL_REVISION}/tokenizer.json',
         ROOT / 'models/param1/tokenizer.json', tokenizer.get('lfs', {}).get('oid'))]
    with ThreadPoolExecutor(max_workers=3) as pool:
        hashes = list(pool.map(lambda job: fetch(*job), jobs))
    extract(ROOT / 'models/llama-cpu.zip', ROOT / '.tools/llama')
    # Keep the downloaded archive local; the evaluation script extracts only test rows.
    manifest = {'base_model': 'bharatgenai/Param-1-2.9B-Instruct',
                'original_tokenizer_revision': ORIGINAL_REVISION,
                'quantization_repository': REPO, 'quantization_revision': REVISION, 'quantization': 'Q4_K_M',
                'dataset': 'ai4bharat/Aksharantar', 'dataset_revision': DATA_REV,
                'runtime': f'ggml-org/llama.cpp {RUNTIME_TAG}',
                'sha256': {str(job[1].relative_to(ROOT)): digest for job, digest in zip(jobs, hashes)}}
    (ROOT / 'data/sovereign_provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Sovereign model and dataset assets ready; hashes verified.', flush=True)


if __name__ == '__main__':
    main()
