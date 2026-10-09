import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request


def xdg(name, fallback):
    value = os.environ.get(name, '')
    return Path(value) if value and Path(value).is_absolute() else Path.home() / fallback


DATA = xdg('XDG_DATA_HOME', '.local/share')
CONFIG = xdg('XDG_CONFIG_HOME', '.config') / 'voice-dictation/models.json'
MODELS = DATA / 'voice-dictation/models'
LEGACY = DATA / 'voxtype/models'
BACKUPS = xdg('XDG_STATE_HOME', '.local/state') / 'voice-dictation/backups'
FILES = ('config.json', 'vocab.txt', 'encoder-model.onnx', 'encoder-model.onnx.data', 'decoder_joint-model.onnx')
REVISION = '8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce'
REPO = 'istupakov/parakeet-tdt-0.6b-v3-onnx'


def validate(folder):
    path = Path(folder).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError('Choose a model folder.')
    missing = [name for name in FILES if not (path / name).is_file() or (path / name).stat().st_size == 0]
    if missing:
        raise ValueError('Incomplete Parakeet ONNX model: missing ' + ', '.join(missing))
    config = json.loads((path / 'config.json').read_text())
    if not isinstance(config, dict) or config.get('model_type') != 'nemo-conformer-tdt' or config.get('features_size') != 128:
        raise ValueError('Only compatible Parakeet TDT ONNX models are supported.')
    return path


def read():
    if not CONFIG.exists():
        return {'selected': '', 'folders': []}
    data = json.loads(CONFIG.read_text())
    if (not isinstance(data, dict) or not isinstance(data.get('selected', ''), str)
            or not isinstance(data.get('folders', []), list)
            or not all(isinstance(folder, str) for folder in data.get('folders', []))):
        raise ValueError('Invalid model settings. Choose a model again to repair them.')
    return data


def selected():
    data = read()
    if data.get('selected'):
        return validate(data['selected'])
    for path in (MODELS / 'parakeet-tdt-0.6b-v3', LEGACY / 'parakeet-tdt-0.6b-v3'):
        try:
            return validate(path)
        except (OSError, ValueError):
            pass
    return None


def commit(folder):
    path = str(validate(folder))
    try:
        data = read()
    except ValueError:
        # Explicit model selection can repair malformed settings, retaining the
        # original bytes outside the source tree before replacing anything.
        BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(prefix='models-invalid-', suffix='.json', dir=BACKUPS, delete=False) as backup:
            backup.write(CONFIG.read_bytes())
        data = {'selected': '', 'folders': []}
    data['selected'] = path
    data['folders'] = sorted(set(data.get('folders', []) + [path]))
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=CONFIG.parent, delete=False) as out:
        json.dump(data, out)
        tmp = Path(out.name)
    try:
        tmp.replace(CONFIG)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def catalog():
    config_error = ''
    try:
        data = read()
    except ValueError:
        data = {'selected': '', 'folders': []}
        config_error = 'Invalid model settings. Choose a model again to repair them.'
    paths = list(data.get('folders', []))
    if data.get('selected'): paths.append(data['selected'])
    for parent in (MODELS, LEGACY):
        if parent.is_dir(): paths.extend(str(p) for p in parent.iterdir() if p.is_dir() and not p.name.startswith('.'))
    found = {}
    for path in paths:
        try:
            folder = validate(path)
            found[str(folder)] = {'value': str(folder), 'label': folder.name}
        except (OSError, ValueError):
            pass
    try:
        current = selected()
    except (OSError, ValueError):
        current = None
    return {'models': list(found.values()), 'selected': str(current) if current else '',
            'configError': config_error,
            'downloadBytes': 2549805955, 'source': 'Hugging Face · istupakov · CC BY 4.0'}


def download(progress, opener=urllib.request.urlopen):
    target = MODELS / 'parakeet-tdt-0.6b-v3'
    if target.exists():
        return str(validate(target))
    MODELS.mkdir(parents=True, exist_ok=True)
    with opener(f'https://huggingface.co/api/models/{REPO}/revision/{REVISION}?blobs=true', timeout=30) as response:
        metadata = json.load(response)
    if metadata.get('sha') != REVISION:
        raise ValueError('Unexpected model revision.')
    entries = {f['rfilename']: f for f in metadata['siblings']}
    total = sum(entries[name]['size'] for name in FILES)
    if shutil.disk_usage(MODELS).free < total + 100 * 1024 * 1024:
        raise ValueError('Not enough disk space to download the model.')
    done = 0
    progress(0, total)
    with tempfile.TemporaryDirectory(prefix='.download-', dir=MODELS) as directory:
        staging = Path(directory)
        for name in FILES:
            entry = entries[name]
            digest = hashlib.sha256() if entry.get('lfs') else hashlib.sha1()
            if not entry.get('lfs'): digest.update(f'blob {entry["size"]}\0'.encode())
            size = 0
            with opener(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}', timeout=30) as response, (staging / name).open('wb') as out:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > entry['size']: raise ValueError('Unexpected download size.')
                    out.write(chunk); digest.update(chunk)
                    done += len(chunk)
                    progress(done, total)
            expected = entry['lfs']['sha256'] if entry.get('lfs') else entry['blobId']
            if size != entry['size'] or digest.hexdigest() != expected:
                raise ValueError('Model integrity check failed: ' + name)
        validate(staging)
        (staging / 'SOURCE.json').write_text(json.dumps({'repository': REPO, 'revision': REVISION, 'license': 'CC-BY-4.0'}))
        if target.exists():
            return str(validate(target))
        staging.rename(target)
    return str(target)
