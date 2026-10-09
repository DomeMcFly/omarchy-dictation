import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import dictation
sys.path.insert(0, str(Path(__file__).parent.parent / 'omarchy-plugin'))
import helper


class PreferenceTests(unittest.TestCase):
    def test_clipboard_owner_does_not_keep_helper_response_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = root / 'voice-dictation'
            history.mkdir()
            (history / 'latest.txt').write_text('Recovery: Grüße')
            clipboard = root / 'wl-copy'
            clipboard.write_text('#!' + sys.executable + '\n'
                'import os, sys, time\n'
                'from pathlib import Path\n'
                'text = sys.stdin.read()\n'
                'Path(os.environ["TEST_COPY"]).write_text(text)\n'
                'pid = os.fork()\n'
                'if pid: sys.exit(0)\n'
                'Path(os.environ["TEST_OWNER"]).write_text(str(os.getpid()))\n'
                'time.sleep(10)\n')
            clipboard.chmod(0o700)
            env = os.environ | {'PATH': str(root) + os.pathsep + os.environ['PATH'],
                'XDG_STATE_HOME': str(root), 'TEST_COPY': str(root / 'copied'),
                'TEST_OWNER': str(root / 'owner')}
            try:
                result = subprocess.run([sys.executable, '-B', helper.__file__, 'copy-last'],
                    env=env, capture_output=True, text=True, timeout=3, check=True)
                self.assertEqual(json.loads(result.stdout), {'ok': True})
                self.assertEqual((root / 'copied').read_text(), 'Recovery: Grüße')
            finally:
                if (root / 'owner').exists():
                    try: os.kill(int((root / 'owner').read_text()), signal.SIGTERM)
                    except ProcessLookupError: pass

    def test_all_panel_preferences_persist_and_backend_reads_transcription(self):
        preferences = dict(position='center-right', margin=109, opacity=61, size=120,
                           style='circle', label=True, monitor='DP-2', enabled=False,
                           animate=False, highlightRecording=False, transcription='after')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch.object(helper, 'CONFIG', path), patch.object(dictation, 'CONFIG', path/'appearance.json'):
                helper.save(preferences)
                self.assertEqual(helper.read(), preferences)
                self.assertEqual(dictation.transcription_mode(), 'after')
                preferences['transcription'] = 'live'
                helper.save(preferences)
                self.assertEqual(dictation.transcription_mode(), 'live')

    def test_invalid_preferences_do_not_overwrite_saved_settings(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(helper, 'CONFIG', Path(directory)):
            helper.save(helper.DEFAULTS)
            for change in ({'transcription': 'other'}, {'enabled': 'false'}, {'style': 'unknown'}):
                with self.assertRaises(ValueError): helper.save(helper.DEFAULTS | change)
            self.assertEqual(helper.read(), helper.DEFAULTS)


if __name__ == '__main__': unittest.main()
