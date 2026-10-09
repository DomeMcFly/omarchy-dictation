import subprocess
import json
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from dictation import Delivery, Session
from streaming import OnlineRecognizer, RATE, Word, pending_words, words_from_result


def hypothesis(text):
    words = text.split()
    return SimpleNamespace(text=text, tokens=[" " + word for word in words],
                           timestamps=[0.2 + index * 0.4 for index in range(len(words))])


class StreamingTests(unittest.TestCase):
    def test_timestamp_drift_does_not_repeat_committed_suffix(self):
        history = [Word("das", .3, .4), Word("ist", .5, .6), Word("ein", .8, .9)]
        current = [Word("das", .3, .4), Word("ist", .6, .7), Word("ein", 1.1, 1.2), Word("Test", 1.5, 1.6)]
        self.assertEqual([w.text for w in pending_words(current, history, 1.0)], ["Test"])

    def test_intentional_repeated_words_are_kept(self):
        history = [Word("ja", .1, .2), Word("ja", .4, .5)]
        current = history + [Word("ja", .7, .8), Word("gut", 1.0, 1.1)]
        self.assertEqual([w.text for w in pending_words(current, history, .6)], ["ja", "gut"])

    def test_subword_and_german_punctuation(self):
        result = SimpleNamespace(tokens=[" Hallo", ",", " W", "elt", "!", " Über", "prüfung"],
                                 timestamps=[0, .1, .3, .4, .5, .7, .8])
        self.assertEqual([w.text for w in words_from_result(result)],
                         ["Hallo,", "Welt!", "Überprüfung"])

    def test_commits_only_agreed_words_and_flushes_tail_once(self):
        model = Mock()
        model.recognize.side_effect = [hypothesis("Ich möchte ein"),
                                       hypothesis("Ich möchte einen Test"),
                                       hypothesis("Ich möchte einen Test machen.")]
        deltas = []
        stream = OnlineRecognizer(model, deltas.append)
        stream.buffer = np.ones(RATE * 4, dtype=np.float32)
        stream.cursor = 4
        stream.decode()
        self.assertEqual(deltas, [])
        stream.decode()
        self.assertEqual(deltas, ["Ich möchte"])
        stream.has_speech = True
        stream.finish()
        stream.finish()
        self.assertEqual("".join(deltas), "Ich möchte einen Test machen.")

    def test_silence_does_not_invoke_model(self):
        model = Mock()
        stream = OnlineRecognizer(model, Mock())
        for _ in range(500):
            stream.feed(np.zeros(320, dtype=np.float32))
        stream.finish()
        model.recognize.assert_not_called()
        self.assertLessEqual(len(stream.buffer), RATE)

    def test_pause_flushes_and_next_sentence_has_one_space(self):
        model = Mock()
        model.recognize.side_effect = [hypothesis("Hallo."), hypothesis("Noch einmal.")]
        deltas = []
        stream = OnlineRecognizer(model, deltas.append, interval=5)
        for _ in range(2):
            for __ in range(20):
                stream.feed(np.ones(320, dtype=np.float32) * .1)
            for __ in range(35):
                stream.feed(np.zeros(320, dtype=np.float32))
        stream.finish()
        self.assertEqual("".join(deltas), "Hallo. Noch einmal.")

    def test_above_threshold_noise_keeps_recording_and_bounded_context(self):
        model = Mock()
        model.recognize.return_value = hypothesis("")
        stream = OnlineRecognizer(model, Mock())
        for _ in range(6000):  # two minutes of energy without recognized words
            stream.feed(np.ones(320, dtype=np.float32) * .01)
            self.assertLess(len(stream.buffer), 16 * RATE)
        self.assertGreater(stream.context_recoveries, 5)
        self.assertEqual(stream.text, "")
        # Real words after the stalled context must still be emitted.
        model.recognize.return_value = hypothesis("Speech resumes.")
        for _ in range(150):
            stream.feed(np.ones(320, dtype=np.float32) * .1)
        stream.finish()
        self.assertEqual(stream.text, "Speech resumes.")

    def test_single_old_word_can_progress_without_waiting_for_next_word(self):
        model = Mock()
        stream = OnlineRecognizer(model, Mock())
        # The one word is at absolute time .2; once its audio has left the
        # window the mock must no longer report it at the new window's start.
        model.recognize.side_effect = lambda *args, **kwargs: hypothesis("Hello" if stream.offset < .2 else "")
        for _ in range(800):
            stream.feed(np.ones(320, dtype=np.float32) * .01)
        stream.finish()
        self.assertEqual(stream.text, "Hello")

    def test_context_overlap_does_not_repeat_already_delivered_word(self):
        model = Mock()
        stream = OnlineRecognizer(model, Mock())
        model.recognize.side_effect = lambda *args, **kwargs: SimpleNamespace(
            tokens=[" Hello"], timestamps=[12.9 - stream.offset])
        stream.buffer = np.ones(RATE * 15, dtype=np.float32)
        stream.cursor = 15
        stream.decode()
        self.assertEqual(stream.text, "Hello")
        # The model sees the same retained audio again, with local timestamps.
        stream.decode(final=True)
        self.assertEqual(stream.text, "Hello")


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.target = {"address": "0x123", "pid": 123}

    def test_long_text_and_unicode_are_delivered_in_order(self):
        run = Mock()
        delivery = Delivery(self.target, Mock(), run=run, focus=lambda: self.target)
        text = "Äpfel, Grüße und Straße. " * 300
        self.assertTrue(delivery.send(text))
        self.assertEqual("".join(call.args[0][-1] for call in run.call_args_list), text)
        self.assertEqual(delivery.delivered, text)
        self.assertTrue(all(len(call.args[0][-1]) <= 120 for call in run.call_args_list))

    def test_focus_change_never_types_into_other_window(self):
        run, failure = Mock(), Mock()
        focus = Mock(side_effect=[self.target, self.target, {"address": "other", "pid": 222}])
        delivery = Delivery(self.target, failure, run=run, focus=focus)
        self.assertFalse(delivery.send("a" * 240))
        self.assertEqual(delivery.delivered, "a" * 120)
        self.assertFalse(delivery.send("more"))
        run.assert_called_once()
        failure.assert_called_once()

    def test_timeout_is_not_retried_or_copied(self):
        run, failure = Mock(side_effect=subprocess.TimeoutExpired("wtype", 30)), Mock()
        delivery = Delivery(self.target, failure, run=run, focus=lambda: self.target)
        self.assertFalse(delivery.send("test"))
        self.assertFalse(delivery.send("again"))
        self.assertEqual(delivery.delivered, "")
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][0], "wtype")

    def test_follow_focus_continues_in_new_window_without_stopping(self):
        second = {"address": "other", "pid": 222}
        current = iter([self.target, second])
        run, failure = Mock(), Mock()
        delivery = Delivery(self.target, failure, run=run,
                            focus=lambda: next(current), follow_focus=True)
        self.assertTrue(delivery.send("a" * 120 + "b" * 120))
        self.assertEqual(delivery.target, second)
        self.assertEqual(delivery.delivered, "a" * 120 + "b" * 120)
        self.assertEqual(run.call_count, 2)
        failure.assert_not_called()

    def test_follow_focus_waits_through_empty_workspace_and_query_failure(self):
        focus = Mock(side_effect=[{}, subprocess.TimeoutExpired('hyprctl', 2), self.target])
        stop = Mock()
        stop.wait.return_value = False
        run, failure = Mock(), Mock()
        delivery = Delivery(self.target, failure, run=run, focus=focus,
                            follow_focus=True, stop_event=stop)
        self.assertTrue(delivery.send("kept until focus returns"))
        self.assertEqual(stop.wait.call_count, 2)
        self.assertFalse(delivery.waiting_for_focus)
        run.assert_called_once()
        failure.assert_not_called()

    def test_stopping_without_a_window_preserves_text_instead_of_hanging(self):
        stop = threading.Event()
        stop.set()
        run, failure = Mock(), Mock()
        delivery = Delivery(self.target, failure, run=run, focus=lambda: {},
                            follow_focus=True, stop_event=stop)
        self.assertFalse(delivery.send("not typed into an unknown surface"))
        self.assertEqual(delivery.delivered, "")
        run.assert_not_called()
        failure.assert_called_once()


class SessionRecoveryTests(unittest.TestCase):
    def test_context_recovery_retains_audio_without_failing_session(self):
        model = Mock()
        model.recognize.return_value = hypothesis("")

        def capture(session):
            # Stand in for PipeWire; exercise real session/recognizer threads.
            (session.path / "audio.wav").write_bytes(b"recovery fixture")
            for _ in range(1500):
                session.frames.put(np.ones(320, dtype=np.float32) * .01)
            session.frames.put(None)

        with tempfile.TemporaryDirectory() as directory, \
                patch('dictation.HISTORY', Path(directory)), \
                patch('dictation.transcription_mode', return_value='live'), \
                patch.object(Session, 'capture_loop', capture), \
                patch('dictation.notify') as notification:
            session = Session(SimpleNamespace(model=model), {"address": "test", "pid": 1})
            session.thread.join(timeout=10)
            self.assertTrue(session.finished)
            result = json.loads((session.path / "result.json").read_text())
            self.assertTrue(result['complete'])
            self.assertGreater(result['context_recoveries'], 0)
            self.assertTrue((session.path / "audio.wav").exists())
            notification.assert_not_called()


if __name__ == "__main__":
    unittest.main()
