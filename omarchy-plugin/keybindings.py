"""Manage only Live Dictation's block in the user's global Hyprland bindings."""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time
import model_store

CONFIG = model_store.xdg('XDG_CONFIG_HOME', '.config')
TARGET = CONFIG / 'hypr/bindings.lua'
BEGIN = '-- BEGIN Live Dictation key bindings'
END = '-- END Live Dictation key bindings'
LEGACY = '-- Register after other unbinds so the F9 callback remains the final override.'
DEFAULTS = dict(primary='F9', alternative='')
MODS = {'SUPER': 64, 'CTRL': 4, 'ALT': 8, 'SHIFT': 1}
ALIASES = {'WIN': 'SUPER', 'META': 'SUPER', 'CONTROL': 'CTRL', 'STRG': 'CTRL'}
KEYS = {'SPACE': 'space', 'RETURN': 'Return', 'ENTER': 'Return', 'TAB': 'Tab',
        'ESCAPE': 'Escape', 'ESC': 'Escape', 'HOME': 'Home', 'END': 'End',
        'PAGEUP': 'Prior', 'PAGEDOWN': 'Next', 'INSERT': 'Insert', 'DELETE': 'Delete',
        'BACKSPACE': 'BackSpace', 'LEFT': 'Left', 'RIGHT': 'Right', 'UP': 'Up', 'DOWN': 'Down',
        'MINUS': 'minus', 'EQUAL': 'equal', 'COMMA': 'comma', 'PERIOD': 'period'}


def normalize(value, optional=False):
    if not isinstance(value, str):
        raise ValueError('Enter a shortcut as text.')
    if not value.strip() and optional:
        return ''
    parts = [ALIASES.get(p.strip().upper(), p.strip().upper()) for p in value.split('+')]
    if 'FN' in parts:
        raise ValueError('Fn is handled by your keyboard. Enter F9, for example, rather than Fn + F9.')
    if not parts or not parts[-1]:
        raise ValueError('A primary shortcut is required.')
    modifiers, key = parts[:-1], parts[-1]
    if any(m not in MODS for m in modifiers) or len(set(modifiers)) != len(modifiers):
        raise ValueError('Use modifiers SUPER, CTRL, ALT or SHIFT, followed by one key.')
    function = re.fullmatch(r'F([1-9]|[12][0-9]|3[0-5])', key)
    if not (function or re.fullmatch(r'[A-Z0-9]', key) or key in KEYS):
        raise ValueError('Use a letter, number, F1–F35, or a named key such as Space or Return.')
    if not function and not any(m in modifiers for m in ('SUPER', 'CTRL', 'ALT')):
        raise ValueError('Use SUPER, CTRL or ALT with this key so normal typing still works.')
    return ' + '.join([m for m in MODS if m in modifiers] + [KEYS.get(key, key)])


def normalized(data):
    result = dict(primary=normalize(data.get('primary', '')),
                  alternative=normalize(data.get('alternative', ''), optional=True))
    if result['primary'] == result['alternative']:
        raise ValueError('Primary and alternative shortcuts must be different.')
    return result


def block_span(text):
    if text.count(BEGIN) == 1 and text.count(END) == 1:
        start, end = text.index(BEGIN), text.index(END) + len(END)
        if end <= start:
            raise ValueError('Invalid managed keybinding block.')
        return start, end
    if BEGIN in text or END in text:
        raise ValueError('Multiple or incomplete Live Dictation keybinding blocks.')
    return len(text), len(text)


def read_text(text):
    start, end = block_span(text)
    block = text[start:end]
    if not block:
        return dict(primary='', alternative='')
    if 'live_dictation_command' not in block or not any(label in block for label in ('Live Dictation: start/stop', 'Dictation: start/stop')):
        raise ValueError('Managed block was modified; review it before changing shortcuts.')
    match = re.search(r'^-- shortcuts: (.+)$', block, re.M)
    if not match:
        raise ValueError('Shortcut metadata is missing.')
    return normalized(json.loads(match.group(1)))


def read():
    return read_text(TARGET.read_text() if TARGET.exists() else "")


def render(data):
    command = shlex.quote(str(Path.home() / '.local/bin/live-dictation')) + ' toggle'
    lines = [BEGIN, '-- shortcuts: ' + json.dumps(data),
             'local live_dictation_command = ' + json.dumps(command)]
    for key in data.values():
        if key:
            lines += ['hl.unbind(' + json.dumps(key) + ')',
                      'o.bind(' + json.dumps(key) + ', "Dictation: start/stop", live_dictation_command, { dont_inhibit = true })']
    return '\n'.join(lines + [END])


def identity(combo):
    parts = combo.split(' + ')
    return sum(MODS[m] for m in parts[:-1]), parts[-1].upper()


def records(raw):
    result, item = [], {}
    for line in raw.splitlines() + ['bind']:
        if line.startswith('bind'):
            if item:
                result.append(item)
            item = {}
        elif line.startswith('\t') and ': ' in line:
            key, value = line[1:].split(': ', 1)
            item[key] = value
    return result


def check_conflicts(data, old, raw, menu="", replace_voxtype=False):
    wanted = {identity(k): k for k in data.values() if k}
    owned = {identity(k) for k in old.values() if k}
    rows = records(raw)
    # Omarchy resolves physical code: bindings against the current keymap.
    for line in menu.splitlines():
        if '→' not in line:
            continue
        combo, description = line.split('→', 1)
        parts = [p.upper() for p in re.split(r'[ +]+', combo.strip()) if p]
        if parts and all(p in MODS for p in parts[:-1]):
            rows.append(dict(modmask=str(sum(MODS[p] for p in parts[:-1])),
                             key=parts[-1], description=description.strip()))
    for row in rows:
        key = row.get('key', '').split(' + ')[-1].upper()
        ident = (int(row.get('modmask', 0)), key)
        if row.get('submap') or ident not in wanted:
            continue
        if ident in owned and row.get('description', '').startswith(('Live Dictation: start/stop', 'Dictation: start/stop')):
            continue
        if replace_voxtype and is_stock_voxtype(row):
            continue
        raise ValueError('Already used: ' + wanted[ident] + ' — ' + row.get('description', 'another global shortcut'))


def is_stock_voxtype(row):
    expected = {
        (0, 'F9'): {'Start dictation (push-to-talk)', 'Stop dictation (push-to-talk)'},
        (68, 'X'): {'Toggle dictation'},
    }
    ident = (int(row.get('modmask', 0)), row.get('key', '').upper())
    if row.get('description') not in expected.get(ident, set()):
        return False
    stock = Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy')) / 'default/hypr/bindings/voxtype.lua'
    if not stock.is_file():
        return False
    text = stock.read_text()
    return all(command in text for command in ('voxtype record start', 'voxtype record stop', 'voxtype record toggle'))


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=10)


def atomic(path, text):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as handle:
        handle.write(text)
        tmp = Path(handle.name)
    try:
        os.chmod(tmp, path.stat().st_mode & 0o777 if path.exists() else 0o600)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def apply(data, replace_voxtype=False, remove=False):
    data = dict(primary="", alternative="") if remove else normalized(data)
    state = CONFIG / 'voice-dictation'
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'keybindings.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        before = TARGET.read_text() if TARGET.exists() else ""
        old = read_text(before)
        if run('hyprctl', 'configerrors').strip():
            raise ValueError('Fix existing Hyprland configuration errors before changing shortcuts.')
        check_conflicts(data, old, run('hyprctl', 'binds'), run('omarchy', 'menu', 'keybindings', '--print'), replace_voxtype)
        start, end = block_span(before)
        replacement = "" if remove else ("\n" if start == len(before) and before and not before.endswith("\n") else "") + render(data)
        after = before[:start] + replacement + before[end:]
        # Parse without executing any commands before touching the live file.
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua') as syntax:
            syntax.write(after); syntax.flush()
            run('luac', '-p', syntax.name)
        backup = state / 'keybindings.before-edit.lua'
        backup.write_text(before)
        if (TARGET.read_text() if TARGET.exists() else "") != before:
            raise ValueError('Keybindings changed elsewhere; reopen settings and try again.')
        atomic(TARGET, after)
        try:
            run('hyprctl', 'reload')
            time.sleep(.2)
            errors = run('hyprctl', 'configerrors').strip()
            if errors:
                raise ValueError(errors)
            actual = { (int(r.get('modmask', 0)), r.get('key', '').split(' + ')[-1].upper())
                       for r in records(run('hyprctl', 'binds'))
                       if r.get('description') in ('Live Dictation: start/stop', 'Dictation: start/stop') }
            expected = {identity(k) for k in data.values() if k}
            if actual != expected:
                raise ValueError('Hyprland did not register the requested shortcuts.')
        except Exception as error:
            if TARGET.read_text() == after:
                atomic(TARGET, before)
                run('hyprctl', 'reload')
                restored_errors = run('hyprctl', 'configerrors').strip()
                if restored_errors:
                    raise ValueError('Restore requires attention: ' + restored_errors) from error
                raise ValueError('Could not apply shortcuts; previous bindings restored. ' + str(error)) from error
            raise ValueError('Keybindings changed elsewhere during apply; the newer file was preserved. ' + str(error)) from error
    return data
