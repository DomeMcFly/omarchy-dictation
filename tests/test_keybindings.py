import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('keys', Path(__file__).parent.parent / 'omarchy-plugin/keybindings.py')
keys = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keys)

class KeybindingTests(unittest.TestCase):
    def test_current_label_and_legacy_block_remain_readable(self):
        rendered = keys.render(keys.DEFAULTS)
        self.assertIn('"Dictation: start/stop"', rendered)
        self.assertEqual(keys.read_text(rendered), keys.DEFAULTS)
        self.assertEqual(keys.read_text(rendered.replace('"Dictation: start/stop"', '"Live Dictation: start/stop"')), keys.DEFAULTS)

    def test_normalization_and_alternative(self):
        self.assertEqual(keys.normalized(dict(primary='ctrl + win + d', alternative='')), dict(primary='SUPER + CTRL + D', alternative=''))
        self.assertEqual(keys.normalize('Strg + Space'), 'CTRL + space')

    def test_invalid_and_injectable_shortcuts_are_rejected(self):
        for value in ('Fn + F9', 'A', 'SHIFT + X', 'SUPER + SUPER + X', 'F9"; os.execute("bad")', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                keys.normalize(value)
        with self.assertRaises(ValueError):
            keys.normalized(dict(primary='F9', alternative='f9'))

    def test_owned_vs_foreign_shortcuts_and_code_resolved_menu(self):
        raw = 'bindd\n\tmodmask: 0\n\tsubmap: \n\tkey: F9\n\tdescription: Live Dictation: start/stop\n'
        keys.check_conflicts(keys.DEFAULTS, keys.DEFAULTS, raw)
        with self.assertRaisesRegex(ValueError, 'Already used'):
            keys.check_conflicts(keys.DEFAULTS, keys.DEFAULTS, raw.replace('Live Dictation: start/stop', 'Other action'))
        with self.assertRaisesRegex(ValueError, 'Already used'):
            keys.check_conflicts(dict(primary='SUPER + K', alternative=''), keys.DEFAULTS, '', 'SUPER + K → Keybindings')

    def test_roundtrip_changes_only_managed_block(self):
        before = 'local unrelated = true\n' + keys.render(keys.DEFAULTS) + '\n-- other settings\n'
        start, end = keys.block_span(before)
        new = dict(primary='SUPER + CTRL + D', alternative='')
        after = before[:start] + keys.render(new) + before[end:]
        self.assertEqual(keys.read_text(after), new)
        self.assertTrue(after.startswith('local unrelated = true\n'))
        self.assertTrue(after.endswith('\n-- other settings\n'))
        self.assertNotIn('Zenbook', after)

    def test_apply_failure_restores_original_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bindings.lua'
            original = '-- unchanged\n' + keys.render(keys.DEFAULTS)
            path.write_text(original)
            errors = iter(['', 'invalid config', ''])
            def run(*args):
                if args == ('hyprctl', 'configerrors'): return next(errors)
                return ''
            with patch.object(keys, 'TARGET', path), patch.object(keys, 'CONFIG', Path(directory)), patch.object(keys, 'run', side_effect=run), patch.object(keys.time, 'sleep'):
                with self.assertRaisesRegex(ValueError, 'previous bindings restored'):
                    keys.apply(dict(primary='SUPER + CTRL + D', alternative=''))
            self.assertEqual(path.read_text(), original)

    def test_rejected_conflict_does_not_touch_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bindings.lua'
            original = keys.render(keys.DEFAULTS)
            path.write_text(original)
            def run(*args):
                if args[:2] == ('omarchy', 'menu'): return 'SUPER + K → Keybindings'
                return ''
            with patch.object(keys, 'TARGET', path), patch.object(keys, 'CONFIG', Path(directory)), patch.object(keys, 'run', side_effect=run):
                with self.assertRaisesRegex(ValueError, 'Already used'):
                    keys.apply(dict(primary='SUPER + K', alternative=''))
            self.assertEqual(path.read_text(), original)

    def test_fresh_configuration_has_no_installed_shortcut(self):
        self.assertEqual(keys.read_text('-- personal bindings\n'), {'primary': '', 'alternative': ''})
        self.assertEqual(keys.block_span('-- personal bindings\n'), (21, 21))

    def test_other_shortcut_does_not_unbind_f9_or_stock_alternative(self):
        rendered = keys.render(dict(primary='SUPER + CTRL + D', alternative=''))
        self.assertNotIn('F9', rendered)
        self.assertNotIn('SUPER + CTRL + X', rendered)
        keys.check_conflicts(dict(primary='SUPER + CTRL + D', alternative=''),
                             dict(primary='', alternative=''),
                             'bindd\n\tmodmask: 0\n\tkey: F9\n\tdescription: Foreign action\n')

    def test_first_install_appends_block_and_uninstall_preserves_personal_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bindings.lua'
            original = '-- personal bindings\n'
            path.write_text(original)
            def run(*args):
                if args == ('hyprctl', 'binds') and keys.BEGIN in path.read_text():
                    return 'bindd\n\tmodmask: 68\n\tkey: D\n\tdescription: Live Dictation: start/stop\n'
                return ''
            with patch.object(keys, 'TARGET', path), patch.object(keys, 'CONFIG', Path(directory)), patch.object(keys, 'run', side_effect=run), patch.object(keys.time, 'sleep'):
                keys.apply(dict(primary='SUPER + CTRL + D', alternative=''))
                self.assertTrue(path.read_text().startswith(original))
                keys.apply({}, remove=True)
            self.assertEqual(path.read_text(), original)

if __name__ == '__main__':
    unittest.main()
