import contextlib
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import dictation


class ShortcutCaptureGuardTests(unittest.TestCase):
    def test_focused_capture_blocks_toggle_and_process_exit_releases_guard(self):
        helper = Path(__file__).resolve().parent.parent / 'omarchy-plugin/helper.py'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / 'voice-dictation'
            env = os.environ | {'XDG_RUNTIME_DIR': str(root)}
            process = subprocess.Popen([sys.executable, '-B', str(helper), 'shortcut-capture'],
                                       env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertTrue(select.select([process.stdout], [], [], 3)[0], 'capture guard did not become ready')
                self.assertEqual(json.loads(process.stdout.readline()), {'ready': True})
                with patch.object(dictation, 'ROOT', runtime), patch.object(dictation, 'HISTORY', root/'history'):
                    self.assertTrue(dictation.shortcut_capture_active())
                    with patch.object(sys, 'argv', ['dictation', 'toggle']), patch.object(dictation, 'client') as client:
                        with contextlib.redirect_stdout(io.StringIO()) as output:
                            dictation.main()
                        self.assertEqual(json.loads(output.getvalue()), {'ignored': 'shortcut-capture'})
                        client.assert_not_called()
                    process.kill()
                    process.wait(timeout=3)
                    self.assertFalse(dictation.shortcut_capture_active())
                    with patch.object(sys, 'argv', ['dictation', 'toggle']), patch.object(dictation, 'client', return_value={'ok': True}) as client:
                        with contextlib.redirect_stdout(io.StringIO()):
                            dictation.main()
                        client.assert_called_once_with('toggle')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=3)
                process.stdout.close()
                process.stderr.close()
