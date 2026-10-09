"""Incremental, append-only transcription using the installed multilingual model.

Two consecutive hypotheses must agree before words are committed. Token times
keep committed audio separate from the rolling context; no backspaces are sent.
"""
from dataclasses import dataclass
import logging
import re
import time

import numpy as np

RATE = 16000
LOG = logging.getLogger(__name__)


@dataclass
class Word:
    text: str
    start: float
    end: float

    @property
    def key(self):
        return re.sub(r"[^\w]", "", self.text).casefold()


def words_from_result(result, offset=0.0):
    """The model uses SentencePiece tokens, decoded with leading spaces."""
    words = []
    for token, stamp in zip(result.tokens or [], result.timestamps or []):
        token = token.replace("▁", " ").replace("<unk>", "")
        if not token.strip():
            continue
        stamp += offset
        if token.startswith(" ") or not words:
            words.append(Word(token.strip(), stamp, stamp + 0.08))
        else:
            words[-1].text += token
            words[-1].end = stamp + 0.08
    return words


def pending_words(words, history, boundary):
    """Align the committed suffix before falling back to noisy token times.

    TDT timestamps move between hypotheses. A timestamp-only cutoff repeats
    words. Lexical anchors disambiguated by time preserve genuine repetitions.
    """
    if not history:
        return words
    for size in range(min(12, len(history)), 0, -1):
        anchor = history[-size:]
        matches = []
        for index in range(len(words) - size + 1):
            candidate = words[index:index + size]
            if [w.key for w in candidate] != [w.key for w in anchor]:
                continue
            drift = abs(candidate[-1].start - anchor[-1].start)
            if drift <= (1.0 if size > 1 else 0.45):
                matches.append((drift, index + size))
        if matches:
            _, end = min(matches)
            return words[end:]
    return [w for w in words if w.start >= boundary]


def load_model(path, threads=4):
    import onnx_asr
    import onnxruntime as ort
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    model = onnx_asr.load_model(
        "nemo-parakeet-tdt-0.6b-v3", path,
        providers=["CPUExecutionProvider"], sess_options=options,
    ).with_timestamps()
    # Warm inference without recording or producing any output.
    model.recognize(np.zeros(RATE, dtype=np.float32), sample_rate=RATE)
    return model


class OnlineRecognizer:
    def __init__(self, model, emit, interval=1.2, silence=0.6, threshold=0.006):
        self.model, self.emit = model, emit
        self.interval, self.silence, self.threshold = interval, silence, threshold
        self.buffer = np.empty(0, dtype=np.float32)
        self.offset = 0.0
        self.cursor = 0.0
        self.last_speech = -100.0
        self.last_decode = 0.0
        self.committed_until = -1.0
        self.previous = []
        self.history = []
        self.has_speech = False
        self.speech_frames = 0
        self.text = ""
        self.context_recoveries = 0

    def feed(self, frame):
        self.buffer = np.concatenate((self.buffer, frame))
        self.cursor += len(frame) / RATE
        rms = float(np.sqrt(np.mean(frame * frame))) if len(frame) else 0.0
        if rms >= self.threshold:
            self.last_speech = self.cursor
            self.speech_frames += len(frame)
            self.has_speech = self.speech_frames >= int(RATE * 0.12)
        if self.has_speech and self.cursor - self.last_speech >= self.silence:
            self.decode(final=True)
            self.reset_segment()
        elif self.has_speech and self.cursor - self.last_decode >= self.interval:
            self.decode()
        elif not self.has_speech and len(self.buffer) > RATE:
            # Retain preroll for quiet beginnings without accumulating silence.
            self.trim(self.cursor - 0.4)

    def trim(self, before):
        count = max(0, min(len(self.buffer), int((before - self.offset) * RATE)))
        self.buffer = self.buffer[count:]
        self.offset += count / RATE

    def decode(self, final=False):
        self.last_decode = self.cursor
        start = time.monotonic()
        result = self.model.recognize(self.buffer, sample_rate=RATE)
        words = pending_words(words_from_result(result, self.offset),
                              self.history, self.committed_until)
        count = len(words) if final else 0
        if not final:
            for old, new in zip(self.previous, words):
                if old.key != new.key or not new.key:
                    break
                count += 1
            # The final word can still be incomplete; allow punctuation to settle.
            count = min(count, max(0, len(words) - 1))
            # In very long uninterrupted speech, force progress only for words
            # with at least two seconds of right context. Memory stays bounded.
            if len(self.buffer) > 14 * RATE:
                count = max(count, sum(w.end < self.cursor - 2.0 for w in words))
        if count:
            selected = words[:count]
            text = " ".join(w.text for w in selected).strip()
            if text:
                delta = (" " if self.text else "") + text
                self.text += delta
                self.emit(delta)
            self.history = (self.history + selected)[-24:]
            if count < len(words):
                self.committed_until = (selected[-1].start + words[count].start) / 2
            else:
                self.committed_until = selected[-1].end
            self.previous = words[count:]
        else:
            self.previous = words
        if not final and len(self.buffer) > 10 * RATE:
            self.trim(max(self.offset, self.committed_until - 2.0))
        # Noise can exceed the energy threshold while producing no words.
        # Refresh that context instead of aborting the microphone session.
        # Keep two seconds of overlap for a quiet/new word at the boundary.
        # Session retains the source audio whenever this recovery is needed.
        if not final and len(self.buffer) > 14 * RATE:
            self.trim(self.cursor - 2.0)
            self.previous = []
            self.context_recoveries += 1
            LOG.warning("Recognition context refreshed; recording continues (recovery=%d)",
                        self.context_recoveries)
        LOG.info("decode audio=%.2fs inference=%.3fs committed_words=%d final=%s",
                 self.cursor - self.offset, time.monotonic() - start, count, final)

    def reset_segment(self):
        self.buffer = np.empty(0, dtype=np.float32)
        self.offset = self.cursor
        self.committed_until = self.cursor
        self.previous = []
        self.history = []
        self.has_speech = False
        self.speech_frames = 0
        self.last_decode = self.cursor

    def finish(self):
        if self.has_speech:
            self.decode(final=True)
        self.reset_segment()
        return self.text
