import tempfile
import threading
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import dictation


class ModeTests(unittest.TestCase):
    def run_session(self, mode, switch_focus=False):
        target = {'address': 'first', 'pid': 1}
        focused = [target]
        calls, typed = [], []
        ready = threading.Event()
        delivery_class = dictation.Delivery
        session_ref = []

        class Recognizer:
            context_recoveries = 0
            def __init__(self, model, emit): self.emit = emit
            def feed(self, frame):
                calls.append('feed')
                if mode == 'after':
                    assert session_ref[0].stop.is_set()
                self.emit('Hallo Welt.')
                if switch_focus: focused[0] = {'address': 'second', 'pid': 2}
            def finish(self): pass

        def capture(session):
            with wave.open(str(session.path / 'audio.wav'), 'wb') as audio:
                audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                audio.writeframes(bytes(640))
                ready.set()
                session.stop.wait(3)
            if mode == 'live': session.frames.put([0.1])
            session.frames.put(None)

        with tempfile.TemporaryDirectory() as directory, patch.object(dictation, 'HISTORY', Path(directory)), patch.object(dictation, 'transcription_mode', return_value=mode), patch.object(dictation, 'active_window', side_effect=lambda: focused[0]), patch.object(dictation.Session, 'capture_loop', capture), patch('streaming.OnlineRecognizer', Recognizer), patch.object(dictation, 'notify'), patch.object(dictation, 'Delivery', side_effect=lambda t, fail, **kw: delivery_class(t, fail, focus=lambda: focused[0], run=lambda args, **kwargs: typed.append(args[-1]), **kw)):
            session = dictation.Session(SimpleNamespace(model=None), target)
            session_ref.append(session)
            self.assertTrue(ready.wait(2))
            self.assertEqual(calls, [])
            self.assertEqual(typed, [])
            session.request_stop()
            session.thread.join(3)
            self.assertTrue(session.finished)
            self.assertEqual(session.text, 'Hallo Welt.')
            if switch_focus:
                self.assertEqual(typed, [])
                self.assertTrue(session.error)
                self.assertTrue((session.path / 'audio.wav').exists())
            else:
                self.assertEqual(typed, ['Hallo Welt.'])
                self.assertFalse(session.error)
                self.assertFalse((session.path / 'audio.wav').exists())

    def test_after_recognizes_only_after_stop_and_delivers_complete_text(self):
        self.run_session('after')

    def test_after_does_not_type_into_changed_window(self):
        self.run_session('after', switch_focus=True)

    def test_live_still_follows_focus(self):
        self.run_session('live', switch_focus=False)

    def test_stop_captures_current_window_once(self):
        session = object.__new__(dictation.Session)
        session.stop = threading.Event()
        session.mode = 'after'
        session.delivery = SimpleNamespace(target={'address': 'old'})
        with patch.object(dictation, 'active_window', return_value={'address': 'new', 'pid': 2}) as focus:
            session.request_stop()
            session.request_stop()
            focus.assert_called_once()
        self.assertEqual(session.delivery.target['address'], 'new')

    def test_cancel_after_recording_stops_decoding_and_retains_audio(self):
        captured = threading.Event()
        ref, feeds, finishes = [], [], []
        class Recognizer:
            context_recoveries = 0
            def __init__(self, model, emit): pass
            def feed(self, frame):
                feeds.append(1)
                ref[0].fail('indicator disconnected')
            def finish(self): finishes.append(1)
        def capture(session):
            with wave.open(str(session.path / 'audio.wav'), 'wb') as audio:
                audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                audio.writeframes(bytes(64000))
            captured.set()
            session.stop.wait(2)
        with tempfile.TemporaryDirectory() as directory, patch.object(dictation, 'HISTORY', Path(directory)), patch.object(dictation, 'transcription_mode', return_value='after'), patch.object(dictation.Session, 'capture_loop', capture), patch('streaming.OnlineRecognizer', Recognizer), patch.object(dictation, 'notify'), patch.object(dictation, 'active_window', return_value={'address': 'test'}):
            session = dictation.Session(SimpleNamespace(model=None), {'address': 'test'})
            ref.append(session)
            self.assertTrue(captured.wait(1))
            session.request_stop()
            session.thread.join(3)
            self.assertTrue(session.finished)
            self.assertEqual(feeds, [1])
            self.assertEqual(finishes, [])
            self.assertTrue((session.path / 'audio.wav').exists())


if __name__ == '__main__':
    unittest.main()
