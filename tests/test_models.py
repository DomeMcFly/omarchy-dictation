import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import dictation
import model_store as store


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(store, 'CONFIG', self.root / 'config/models.json'),
                        patch.object(store, 'MODELS', self.root / 'models'),
                        patch.object(store, 'LEGACY', self.root / 'legacy'),
                        patch.object(store, 'BACKUPS', self.root / 'backups'),
                        patch.object(dictation, 'ROOT', self.root)]
        for item in self.patches: item.start()
        self.addCleanup(self.temp.cleanup)
        for item in self.patches: self.addCleanup(item.stop)

    def folder(self, parent):
        parent.mkdir(parents=True)
        for name in store.FILES: (parent / name).write_bytes(b'model fixture')
        (parent / 'config.json').write_text(json.dumps({'model_type': 'nemo-conformer-tdt', 'features_size': 128}))
        return parent

    def test_no_model_daemon_stays_available(self):
        daemon = dictation.Daemon()
        self.assertIsNone(store.selected())
        self.assertEqual(daemon.command({'action': 'status'})['state'], 'no-model')
        self.assertIn('error', daemon.command({'action': 'toggle'}))

    def test_existing_model_discovery_and_saved_selection(self):
        first = self.folder(store.LEGACY / 'parakeet-tdt-0.6b-v3')
        second = self.folder(self.root / 'external model')
        self.assertEqual(store.selected(), first)
        store.commit(second)
        self.assertEqual(store.selected(), second)
        self.assertEqual(len(store.catalog()['models']), 2)

    def test_failed_model_load_preserves_active_and_saved_model(self):
        original = self.folder(store.MODELS / 'original')
        candidate = self.folder(store.MODELS / 'candidate')
        store.commit(original)
        daemon = dictation.Daemon()
        active = object()
        daemon.model, daemon.model_path = active, str(original)
        with patch('streaming.load_model', side_effect=RuntimeError('Invalid ONNX')):
            daemon.select_model(candidate)
            daemon.model_thread.join(2)
        self.assertIs(daemon.model, active)
        self.assertEqual(store.selected(), original)
        self.assertTrue(daemon.model_error)
        self.assertEqual(daemon.write_state()['state'], 'idle')

    def test_successful_model_load_persists_only_after_validation(self):
        candidate = self.folder(store.MODELS / 'candidate')
        daemon = dictation.Daemon()
        active = object()
        with patch('streaming.load_model', return_value=active):
            daemon.select_model(candidate)
            daemon.model_thread.join(2)
        self.assertIs(daemon.model, active)
        self.assertEqual(store.selected(), candidate)
        self.assertEqual(daemon.write_state()['state'], 'idle')

    def test_incomplete_folder_rejected(self):
        candidate = self.folder(self.root / 'incomplete')
        (candidate / 'vocab.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'missing'): store.commit(candidate)
        self.assertFalse(store.CONFIG.exists())

    def test_invalid_model_metadata_does_not_hide_other_models(self):
        good = self.folder(store.MODELS / 'good')
        bad = self.folder(store.MODELS / 'bad')
        (bad / 'config.json').write_text('[]')
        self.assertEqual(store.catalog()['models'], [{'value': str(good), 'label': 'good'}])

    def test_invalid_settings_can_be_repaired_by_explicit_selection(self):
        good = self.folder(store.MODELS / 'good')
        store.CONFIG.parent.mkdir(parents=True)
        for invalid in ('[]', '{broken', '{"selected": 9}', '{"folders": [5]}'):
            with self.subTest(invalid=invalid):
                store.CONFIG.write_text(invalid)
                with self.assertRaises(ValueError): store.selected()
                self.assertTrue(store.catalog()['configError'])
                self.assertEqual(len(store.catalog()['models']), 1)
                store.commit(good)
                self.assertEqual(store.selected(), good)
                self.assertIn(invalid, [p.read_text() for p in store.BACKUPS.glob('*.json')])

    def test_model_load_failure_without_fallback_is_not_no_model_or_ready(self):
        candidate = self.folder(store.MODELS / 'unloadable')
        daemon = dictation.Daemon()
        with patch('streaming.load_model', side_effect=RuntimeError('Invalid ONNX')):
            daemon.select_model(candidate)
            daemon.model_thread.join(2)
        state = daemon.command({'action': 'status'})
        self.assertEqual(state['state'], 'model-error')
        self.assertTrue(state['model_error'])
        self.assertIn('error', daemon.command({'action': 'toggle'}))

    def test_model_is_not_ready_until_warmup_finishes(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        candidate = self.folder(store.MODELS / 'warming')
        daemon = dictation.Daemon()
        def load(path):
            entered.set()
            release.wait(2)
            return object()
        with patch('streaming.load_model', side_effect=load):
            try:
                daemon.select_model(candidate)
                self.assertTrue(entered.wait(1))
                self.assertEqual(daemon.write_state()['state'], 'loading')
                self.assertIn('error', daemon.command({'action': 'toggle'}))
            finally:
                release.set()
                daemon.model_thread.join(2)
        self.assertEqual(daemon.write_state()['state'], 'idle')

    def download_fixture(self, corrupt=False):
        content = {name: b'model fixture' for name in store.FILES}
        content['config.json'] = json.dumps({'model_type': 'nemo-conformer-tdt', 'features_size': 128}).encode()
        entries = [{'rfilename': name, 'size': len(data), 'blobId': hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()} for name, data in content.items()]
        metadata = {'sha': store.REVISION, 'siblings': entries}
        def opener(url, **kwargs):
            if '/api/' in url: return io.BytesIO(json.dumps(metadata).encode())
            data = content[url.rsplit('/', 1)[1]]
            return io.BytesIO(b'x' * len(data) if corrupt else data)
        return opener

    def test_verified_download_promotes_complete_directory(self):
        progress = []
        path = store.download(lambda done, total: progress.append((done, total)), self.download_fixture())
        self.assertTrue(store.validate(path))
        self.assertEqual(progress[-1][0], progress[-1][1])
        self.assertFalse(list(store.MODELS.glob('.download-*')))

    def test_corrupt_download_is_not_installable(self):
        with self.assertRaisesRegex(ValueError, 'integrity'):
            store.download(lambda *args: None, self.download_fixture(corrupt=True))
        self.assertEqual(store.catalog()['models'], [])
        self.assertFalse(list(store.MODELS.glob('.download-*')))


if __name__ == '__main__': unittest.main()
