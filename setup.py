#!/usr/bin/env python3
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
import model_store

SOURCE = Path(__file__).resolve().parent
PLUGIN_ID = 'dominic.live-dictation'
RUNTIME_FILES = ('dictation.py', 'streaming.py', 'model_store.py', 'requirements.lock')
RELEASE_FILES = ('.gitignore', 'manifest.json', 'setup.py', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
                 'requirements.txt', 'requirements.lock', 'docs/TESTING.md', 'docs/RELEASE_CHECKLIST.md',
                 'dictation.py', 'streaming.py', 'model_store.py',
                 'docs/USER_GUIDE.md', 'preview.png')
COMMANDS = ('uv', 'pw-record', 'wtype', 'hyprctl', 'omarchy', 'omarchy-shell',
            'systemctl', 'wl-copy', 'xdg-open', 'luac')


def paths():
    config = model_store.xdg('XDG_CONFIG_HOME', '.config')
    data = model_store.xdg('XDG_DATA_HOME', '.local/share') / 'voice-dictation'
    state = model_store.xdg('XDG_STATE_HOME', '.local/state') / 'voice-dictation'
    return dict(config=config, data=data, state=state, runtime=data / 'runtime',
                plugin=config / 'omarchy/plugins' / PLUGIN_ID,
                unit=config / 'systemd/user/voice-dictation.service',
                launcher=Path.home() / '.local/bin/live-dictation', ledger=state / 'installation.json')


def run(*args, check=True):
    env = os.environ.copy()
    if args and args[0] in ('omarchy', 'omarchy-shell'):
        env['OMARCHY_SHELL_IPC_TIMEOUT'] = '15s'
    result = subprocess.run([str(a) for a in args], check=check, text=True, capture_output=True, env=env)
    return result.stdout.strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def release_files():
    files = [SOURCE / name for name in RELEASE_FILES]
    files.extend(p for p in (SOURCE / 'omarchy-plugin').rglob('*')
                 if p.is_file() and p.suffix in ('.py', '.qml', '.js', '.md') and '__pycache__' not in p.parts)
    files.extend(p for p in (SOURCE / 'tests').rglob('*')
                 if p.is_file() and (p.suffix in ('.py', '.qml') or p.name == 'qmldir') and '__pycache__' not in p.parts)
    for p in files:
        if not p.is_file() or p.is_symlink():
            raise RuntimeError(f'Release file is missing or a symlink: {p}')
    return files


def export(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise RuntimeError('Export destination must not exist.')
    destination.mkdir(parents=True)
    for source in release_files():
        target = destination / source.relative_to(SOURCE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return destination


def check_dependencies():
    missing = [name for name in COMMANDS if not shutil.which(name)]
    if missing:
        raise RuntimeError('Missing commands: ' + ', '.join(missing) + '. See README prerequisites.')
    print('Required desktop commands are available.')


def atomic(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def unit_text(runtime, python_path=None):
    python_path = python_path or runtime / "venv/bin/python"
    def quote(path):
        if any(c in str(path) for c in ("\n", "\r", "\0")):
            raise ValueError("Installation paths must not contain control characters.")
        return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
    return f'''# Managed by Live Dictation setup.py
[Unit]
Description=Local speech-to-text for Omarchy
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart={quote(python_path)} {quote(runtime / 'dictation.py')} serve
Environment=PYTHONUNBUFFERED=1
Environment=OMP_NUM_THREADS=4
Environment={quote('XDG_CONFIG_HOME=' + str(model_store.xdg('XDG_CONFIG_HOME', '.config')))}
Environment={quote('XDG_DATA_HOME=' + str(model_store.xdg('XDG_DATA_HOME', '.local/share')))}
Environment={quote('XDG_STATE_HOME=' + str(model_store.xdg('XDG_STATE_HOME', '.local/state')))}
UMask=0077
Restart=on-failure
RestartSec=3
TimeoutStopSec=70

[Install]
WantedBy=graphical-session.target
'''


def ensure_idle():
    sys.path.insert(0, str(SOURCE / 'omarchy-plugin'))
    import helper
    try:
        status = helper.request('status')
    except (FileNotFoundError, ConnectionRefusedError):
        return
    if status.get('state') in ('recording', 'finishing', 'transcribing', 'loading'):
        raise RuntimeError('Finish the active dictation/model loading before setup or removal.')


def plugin_placement(config):
    path = config / 'omarchy/shell.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    for section, entries in data.get('bar', {}).get('layout', {}).items():
        for index, entry in enumerate(entries):
            if entry.get('id') == PLUGIN_ID:
                args = ['--section', section]
                if index + 1 < len(entries):
                    args += ['--before', entries[index + 1]['id']]
                return args
    return None


def install(python='3.12', shortcut=None, replace_voxtype=False):
    check_dependencies()
    ensure_idle()
    loc = paths()
    for name in ('data', 'state'):
        loc[name].mkdir(parents=True, exist_ok=True, mode=0o700)
    ledger = json.loads(loc['ledger'].read_text()) if loc['ledger'].exists() else {'files': {}}
    placement = plugin_placement(loc['config'])
    # Refuse overwriting an unrelated launcher or service.
    for name in ('launcher', 'unit'):
        path = loc[name]
        if path.exists() and str(path) not in ledger['files']:
            text = path.read_text()
            if 'voice-dictation/dictation.py' not in text and 'Managed by Live Dictation' not in text:
                raise RuntimeError(f'Unmanaged file already exists: {path}')
    if loc['plugin'].exists() and loc['plugin'].resolve() != SOURCE:
        manifest = loc['plugin'] / 'manifest.json'
        if not manifest.is_file() or json.loads(manifest.read_text()).get('id') != PLUGIN_ID:
            raise RuntimeError('Plugin destination belongs to another application.')
        if (loc['plugin'] / '.git').exists():
            raise RuntimeError('Run setup.py from the installed git plugin checkout to preserve its update history.')
    # Preserve edits made outside setup instead of overwriting them on update.
    for name, entry in ledger['files'].items():
        path = Path(name)
        if loc['plugin'].resolve() == SOURCE and path.is_relative_to(SOURCE):
            continue
        if path.exists() and digest(path) != entry.get('installed_sha256'):
            source = SOURCE / path.relative_to(loc['plugin']) if path.is_relative_to(loc['plugin']) else None
            if source is None or not source.is_file() or digest(source) != digest(path):
                raise RuntimeError(f'Installed file was modified; preserve/reconcile it before update: {path}')
    # Complete dependency installation before changing the running service.
    runtime = loc['runtime']
    runtime.mkdir(parents=True, exist_ok=True)
    lock_hash = hashlib.sha256((SOURCE / 'requirements.lock').read_bytes()).hexdigest()[:16]
    environment = runtime / 'environments' / lock_hash
    environment_ready = environment / '.ready'
    if not environment_ready.exists():
        if environment.exists():
            shutil.rmtree(environment)
        environment.parent.mkdir(parents=True, exist_ok=True)
        try:
            run('uv', 'venv', '--python', python, environment)
            run('uv', 'pip', 'sync', '--python', environment / 'bin/python', SOURCE / 'requirements.lock')
            run(environment / 'bin/python', '-c', 'import numpy, onnxruntime, onnx_asr')
            environment_ready.write_text(lock_hash)
        except Exception:
            if environment.exists(): shutil.rmtree(environment)
            raise
    ledger['environments'] = sorted(set(ledger.get('environments', []) + [str(environment)]))
    staged = Path(tempfile.mkdtemp(prefix='install-', dir=loc['state']))
    rollback = []
    service_was_active = run('systemctl', '--user', 'is-active', 'voice-dictation.service', check=False) == 'active'
    try:
        payload = export(staged / 'plugin')
        run('omarchy', 'plugin', 'validate', payload)
        backups = loc['state'] / 'backups' / time.strftime('%Y%m%d-%H%M%S')
        backups.mkdir(parents=True, exist_ok=True)
        def write(path, content, mode=0o600):
            if path.exists() and path.read_bytes() == content:
                if str(path) in ledger['files']:
                    ledger['files'][str(path)]['installed_sha256'] = digest(path)
                return
            prior = path.read_bytes() if path.exists() else None
            prior_mode = path.stat().st_mode & 0o777 if path.exists() else mode
            rollback.append((path, prior, prior_mode))
            key = str(path)
            if key not in ledger['files']:
                backup = backups / str(len(ledger['files']))
                if prior is not None:
                    backup.write_bytes(prior)
                ledger['files'][key] = {'backup': str(backup) if prior is not None else None, 'mode': prior_mode}
            atomic(path, content, mode)
            ledger['files'][key]['installed_sha256'] = digest(path)
        run('omarchy', 'plugin', 'disable', PLUGIN_ID, check=False)
        run('systemctl', '--user', 'stop', 'voice-dictation.service', check=False)
        for name in RUNTIME_FILES:
            write(runtime / name, (SOURCE / name).read_bytes())
        if loc['plugin'].resolve() != SOURCE:
            for source in payload.rglob('*'):
                if source.is_file():
                    write(loc['plugin'] / source.relative_to(payload), source.read_bytes())
        write(loc['unit'], unit_text(runtime, environment / 'bin/python').encode())
        launcher = '#!/bin/sh\n# Managed by Live Dictation setup.py\nexec ' + shlex.quote(str(environment / 'bin/python')) + ' ' + shlex.quote(str(runtime / 'dictation.py')) + ' "$@"\n'
        write(loc['launcher'], launcher.encode(), 0o755)
        run('systemctl', '--user', 'daemon-reload')
        run('systemctl', '--user', 'enable', '--now', 'voice-dictation.service')
        run('omarchy-shell', 'shell', 'rescanPlugins')
        run('omarchy', 'plugin', 'enable', PLUGIN_ID, *(placement or ['--section', 'right', '--before', 'omarchy.audio']))
        atomic(loc['ledger'], (json.dumps(ledger, indent=2) + '\n').encode())
    except Exception:
        run('systemctl', '--user', 'stop', 'voice-dictation.service', check=False)
        for path, prior, mode in reversed(rollback):
            if prior is None:
                path.unlink(missing_ok=True)
            else:
                atomic(path, prior, mode)
        run('systemctl', '--user', 'daemon-reload', check=False)
        if service_was_active:
            run('systemctl', '--user', 'start', 'voice-dictation.service', check=False)
        elif not loc['unit'].exists():
            run('systemctl', '--user', 'disable', 'voice-dictation.service', check=False)
        run('omarchy-shell', 'shell', 'rescanPlugins', check=False)
        if placement is not None:
            run('omarchy', 'plugin', 'enable', PLUGIN_ID, *placement, check=False)
        else:
            run('omarchy', 'plugin', 'disable', PLUGIN_ID, check=False)
        raise
    finally:
        shutil.rmtree(staged)
    sys.path.insert(0, str(SOURCE / 'omarchy-plugin'))
    import keybindings
    try:
        current = keybindings.read()
        desired = shortcut or current['primary'] or 'F9'
        keybindings.apply({'primary': desired, 'alternative': ''}, replace_voxtype=replace_voxtype)
    except (ValueError, subprocess.SubprocessError) as error:
        print('Installed; shortcut was not changed: ' + str(error))
        print('Choose an unused shortcut in settings, or explicitly migrate a stock Voxtype binding.')
    print('Dictation installed. Choose or download a model in the microphone panel.')
    print('After an update, run omarchy restart shell to refresh cached UI components.')


def uninstall():
    ensure_idle()
    loc = paths()
    if not loc['ledger'].exists():
        raise RuntimeError('Installation record missing. Refusing to guess which files to remove.')
    ledger = json.loads(loc['ledger'].read_text())
    sys.path.insert(0, str(SOURCE / 'omarchy-plugin'))
    import keybindings
    keybindings.apply({}, remove=True)
    run('omarchy', 'plugin', 'disable', PLUGIN_ID)
    run('systemctl', '--user', 'disable', '--now', 'voice-dictation.service')
    changed = []
    for name, entry in ledger['files'].items():
        path = Path(name)
        if not path.exists():
            continue
        if digest(path) != entry.get('installed_sha256'):
            changed.append(name)
            continue
        # Keep old development files in backups, not active on uninstall.
        path.unlink()
        if path.suffix == '.py' and path.is_relative_to(loc['plugin']):
            # Only derived bytecode for files we actually removed. Unrelated
            # files in a plugin directory must remain untouched.
            for cache in (path.parent / '__pycache__').glob(path.stem + '.*.pyc'):
                cache.unlink()
    if loc['plugin'].exists():
        for directory in sorted((p for p in loc['plugin'].rglob('*') if p.is_dir()),
                                key=lambda p: len(p.parts), reverse=True):
            try: directory.rmdir()
            except OSError: pass
        try: loc['plugin'].rmdir()
        except OSError: pass
    run('systemctl', '--user', 'daemon-reload')
    # The venv belongs exclusively to this installer. Models/history are separate.
    for directory in ledger.get('environments', []):
        environment = Path(directory)
        if environment.parent == loc['runtime'] / 'environments' and environment.exists():
            shutil.rmtree(environment)
    if changed:
        print('Preserved modified files: ' + ', '.join(changed))
    else:
        loc['ledger'].unlink()
    print('Removed service, launcher, and managed shortcut. Models, settings, history and backups retained.')
    print('If installed through Omarchy git, now run: omarchy plugin remove ' + PLUGIN_ID)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='Install, update or remove Dictation for the current user.')
    parser.add_argument('action', choices=('check', 'install', 'update', 'uninstall', 'export'))
    parser.add_argument('--python', default='3.12')
    parser.add_argument('--shortcut')
    parser.add_argument('--replace-voxtype', action='store_true', help='Explicitly replace a verified stock Voxtype shortcut only.')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'check': check_dependencies()
        elif args.action in ('install', 'update', 'uninstall'):
            state = paths()['state']
            state.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (state / 'setup.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if args.action == 'uninstall': uninstall()
                else: install(args.python, args.shortcut, args.replace_voxtype)
        elif args.output: print(export(args.output))
        else: parser.error('export requires --output')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr or error.stdout or '', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
