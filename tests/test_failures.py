import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import dictation


class FailureTests(unittest.TestCase):
    def test_output_drain_allows_progress_beyond_initial_deadline(self):
        session = object.__new__(dictation.Session)
        session.delivery = SimpleNamespace(delivered='')
        session.fail = Mock()
        clock = [0.0]
        worker = Mock()
        worker.is_alive.side_effect = lambda: clock[0] < 100
        def join(timeout):
            clock[0] += 10
            session.delivery.delivered += 'chunk'
        worker.join.side_effect = join
        with patch.object(dictation.time, 'monotonic', side_effect=lambda: clock[0]):
            session.drain_output(worker)
        self.assertEqual(clock[0], 100)
        session.fail.assert_not_called()

    def test_output_drain_bounds_a_stalled_worker(self):
        session = object.__new__(dictation.Session)
        session.delivery = SimpleNamespace(delivered='')
        session.fail = Mock()
        clock = [0.0]
        worker = Mock()
        worker.is_alive.return_value = True
        def join(timeout): clock[0] += 10
        worker.join.side_effect = join
        with patch.object(dictation.time, 'monotonic', side_effect=lambda: clock[0]):
            session.drain_output(worker)
        session.fail.assert_called_once()
        self.assertLess(clock[0], 60)

    def exercise(self, failed_file=None, constructor_failure=False):
        original_atomic = dictation.atomic
        typed = []
        first_write = threading.Event()

        def atomic(path, text):
            if path.name == failed_file:
                first_write.set()
                raise OSError('simulated disk failure')
            original_atomic(path, text)

        class Recognizer:
            context_recoveries = 0
            def __init__(self, model, emit):
                if constructor_failure:
                    raise RuntimeError('initialization failed')
                self.emit = emit
            def feed(self, frame):
                self.emit('first ')
                if failed_file == 'delivered.txt':
                    first_write.wait(2)
                self.emit('remaining')
            def finish(self): pass

        def capture(session):
            (session.path / 'audio.wav').write_bytes(b'audio retained on failure')
            session.frames.put([0.1])

        with tempfile.TemporaryDirectory() as directory, patch.object(dictation, 'HISTORY', Path(directory)), patch.object(dictation, 'transcription_mode', return_value='live'), patch.object(dictation.Session, 'capture_loop', capture), patch('streaming.OnlineRecognizer', Recognizer), patch.object(dictation, 'atomic', side_effect=atomic), patch.object(dictation, 'notify'):
            real_delivery = dictation.Delivery
            target = {'address': 'test', 'pid': 1}
            with patch.object(dictation, 'Delivery', side_effect=lambda t, fail, **kw: real_delivery(t, fail, run=lambda args, **kwargs: typed.append(args[-1]), focus=lambda: target, **kw)):
                session = dictation.Session(SimpleNamespace(model=None), target)
                session.thread.join(4)
            self.assertFalse(session.thread.is_alive())
            self.assertTrue(session.finished)
            self.assertTrue(session.error)
            if not constructor_failure:
                self.assertTrue((session.path / 'audio.wav').exists())
            result = session.path / 'result.json'
            if result.exists(): self.assertFalse(json.loads(result.read_text())['complete'])
            self.assertTrue((Path(directory) / 'recovery.json').exists())
            if failed_file == 'delivered.txt': self.assertEqual(typed, ['first '])

    def test_delivery_journal_failure_is_not_success(self): self.exercise('delivered.txt')
    def test_result_failure_always_finishes_and_retains_audio(self): self.exercise('result.json')
    def test_transcript_failure_retains_audio(self): self.exercise('transcript.txt')
    def test_recognizer_construction_failure_always_finishes(self): self.exercise(constructor_failure=True)

    def test_focus_change_inside_output_is_uncertain_not_success(self):
        target = {'address': 'one', 'pid': 1}
        current = [target]
        def run(*args, **kwargs): current[0] = {'address': 'two', 'pid': 2}
        failure = Mock()
        delivery = dictation.Delivery(target, failure, run=run, focus=lambda: current[0])
        self.assertFalse(delivery.send('ambiguous'))
        self.assertEqual(delivery.delivered, '')
        failure.assert_called_once()

    def test_running_output_is_killed_when_focus_changes(self):
        target = {'address': 'one', 'pid': 1}
        process = Mock()
        process.poll.return_value = None
        process.__enter__ = Mock(return_value=process)
        process.__exit__ = Mock(return_value=False)
        focus = Mock(side_effect=[target, {'address': 'two', 'pid': 2}])
        with patch.object(dictation.subprocess, 'Popen', return_value=process):
            delivery = dictation.Delivery(target, Mock(), focus=focus)
            self.assertFalse(delivery.send('test'))
        process.kill.assert_called_once()

    def test_printable_keys_never_use_physical_control_slots(self):
        text = 'Browser dictation: Grüße und Äpfel.'
        args = dictation.wtype_command(text)[1:]
        reserved = []
        presses = []
        for flag, value in zip(args[::2], args[1::2]):
            (reserved if flag == '-p' else presses).append(value)
        slots = {name: index + 1 for index, name in enumerate(reserved)}
        self.assertTrue(all(slots[name] in dictation.TEXT_KEY_SLOTS for name in presses))
        self.assertEqual(''.join(chr(int(name[1:], 16)) for name in presses), text)

    def test_many_distinct_unicode_characters_are_bounded_without_loss(self):
        text = ''.join(chr(0x400 + i) for i in range(220))
        chunks = list(dictation.delivery_chunks(text))
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(c) <= 120 and len(set(c)) <= len(dictation.TEXT_KEY_SLOTS) for c in chunks))
        for chunk in chunks: dictation.wtype_command(chunk)

    def test_old_frontend_cannot_cancel_new_frontend(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(dictation, 'ROOT', Path(directory)):
            daemon = dictation.Daemon()
            session = Mock(finished=False)
            daemon.session = session
            daemon.command({'action': 'frontend', 'token': 'old'})
            daemon.command({'action': 'frontend', 'token': 'new'})
            daemon.command({'action': 'frontend-stop', 'token': 'old'})
            session.fail.assert_not_called()
            daemon.command({'action': 'frontend-stop', 'token': 'new'})
            session.fail.assert_called_once()
            self.assertFalse(daemon.frontend_available())

    def test_recording_requires_visible_frontend(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(dictation, 'ROOT', Path(directory)):
            daemon = dictation.Daemon()
            daemon.model = object()
            self.assertIn('Enable', daemon.command({'action': 'toggle'})['error'])


if __name__ == '__main__': unittest.main()
