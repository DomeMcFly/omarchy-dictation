#!/usr/bin/env python3
"""Local-only plugin persistence/control. Never starts an audio recording."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import model_store

CONFIG = model_store.xdg('XDG_CONFIG_HOME', '.config') / 'voice-dictation'
RUNTIME = model_store.xdg('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}') / 'voice-dictation'
HISTORY = model_store.xdg('XDG_STATE_HOME', '.local/state') / 'voice-dictation'
DEFAULTS = dict(position='bottom-center', margin=64, opacity=85, size=100,
                style='wave', label=False, monitor='', enabled=True, animate=True, highlightRecording=True, transcription="live")

def normalized(data):
    result = DEFAULTS | {k: v for k, v in data.items() if k in DEFAULTS}
    if result['position'] not in [f'{y}-{x}' for y in ('top','center','bottom') for x in ('left','center','right')]:
        raise ValueError('Invalid position')
    if result['transcription'] not in ('live', 'after'):
        raise ValueError('Invalid transcription mode')
    if result['style'] not in ('wave','compact','circle'):
        raise ValueError('Invalid style')
    for key, low, high in [('margin',0,300),('opacity',15,100),('size',60,180)]:
        result[key] = max(low,min(high,int(result[key])))
    for key in ('label','enabled','animate','highlightRecording'):
        if not isinstance(result[key],bool):
            raise ValueError(f'{key} must be a boolean')
    if not isinstance(result['monitor'],str):
        raise ValueError('Invalid monitor')
    return result

def read():
    path = CONFIG / 'appearance.json'
    return normalized(json.loads(path.read_text()) if path.exists() else {})

def save(data):
    data = normalized(data)
    CONFIG.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=CONFIG,delete=False) as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        tmp=Path(f.name)
    tmp.replace(CONFIG/'appearance.json')
    return data

def request(action, **payload):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(3)
        sock.connect(str(RUNTIME/'control.sock'))
        sock.sendall(json.dumps({'action':action, **payload}).encode())
        result=json.loads(sock.recv(4096))
    if result.get('error'):
        raise RuntimeError(result['error'])
    return result

def main():
    os.umask(0o077)
    action=sys.argv[1]
    if action.startswith('model-'):
        import model_store
        if action == 'model-list': return model_store.catalog()
        if action == 'model-select':
            from urllib.parse import urlparse, unquote
            path = sys.argv[2]
            if path.startswith('file:'): path = unquote(urlparse(path).path)
            return request('model-select', path=str(model_store.validate(path)))
        if action == 'model-download':
            import fcntl
            model_store.MODELS.mkdir(parents=True, exist_ok=True)
            with (model_store.MODELS / '.download.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                previous = [-1]
                def progress(done, total):
                    percent = int(done * 100 / total)
                    if percent != previous[0]:
                        print(json.dumps({'progress': percent}), flush=True)
                        previous[0] = percent
                return {'downloaded': model_store.download(progress)}
        raise ValueError('Unknown model action')
    if action in ('keys-read' , 'keys-save'):
        import keybindings
        return keybindings.read() if action == 'keys-read' else keybindings.apply(json.loads(sys.argv[2]))
    if action=='read': return read()
    if action=='save': return save(json.loads(sys.argv[2]))
    if action in ('frontend', 'frontend-stop'): return request(action, token=sys.argv[2])
    if action in ('status','stop','dismiss-recovery'): return request(action)
    if action=='start-service':
        subprocess.run(['systemctl','--user','start','voice-dictation.service'],check=True,timeout=10)
    elif action=='open-history':
        HISTORY.mkdir(parents=True,exist_ok=True)
        subprocess.Popen(['xdg-open',str(HISTORY)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    elif action=='copy-last':
        text=(HISTORY/'latest.txt').read_text()
        # wl-copy forks a clipboard owner. It must not inherit the helper's
        # JSON output pipe, or the panel's collector waits until ownership ends.
        subprocess.run(['wl-copy'],input=text,text=True,check=True,timeout=5,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else:
        raise ValueError('Unknown action')
    return {'ok':True}

if __name__=='__main__':
    try:
        print(json.dumps(main(),ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'error':str(e)},ensure_ascii=False))
        raise SystemExit(1)
