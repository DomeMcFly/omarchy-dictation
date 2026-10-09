#!/usr/bin/env python3
"""Local dictation service. Audio, inference and delivery run independently."""
import argparse
import fcntl
import json
import logging
import os
from pathlib import Path
import queue
import select
import signal
import socket
import subprocess
import threading
import time
import uuid
import wave
import model_store

ROOT = model_store.xdg("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}") / "voice-dictation"
HISTORY = model_store.xdg("XDG_STATE_HOME", ".local/state") / "voice-dictation"
CONFIG = model_store.xdg("XDG_CONFIG_HOME", ".config") / "voice-dictation/appearance.json"
LOG = logging.getLogger("dictation")


def transcription_mode():
    if not CONFIG.exists():
        return "live"
    mode = json.loads(CONFIG.read_text()).get("transcription", "live")
    if mode not in ("live", "after"):
        raise ValueError("Invalid transcription mode")
    return mode


def atomic(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def active_window():
    result = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True,
                            text=True, check=True, timeout=2)
    window = json.loads(result.stdout)
    return {key: window.get(key) for key in ("address", "pid")}


def notify(message):
    try:
        subprocess.run(["notify-send", "Dictation", message], timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        LOG.warning("Notification unavailable")


TEXT_KEY_SLOTS = tuple(list(range(2, 14)) + list(range(16, 28)) + list(range(30, 42)) + [43] + list(range(44, 54)) + [57])


def delivery_chunks(text):
    chunk, characters = "", set()
    for character in text:
        if len(chunk) >= 120 or (character not in characters and len(characters) >= len(TEXT_KEY_SLOTS)):
            yield chunk
            chunk, characters = "", set()
        chunk += character
        characters.add(character)
    if chunk:
        yield chunk


def wtype_command(text):
    # Chromium interprets some physical control-key positions even when wtype
    # supplies a printable keysym. Reserve those positions with release-only
    # placeholders and emit text using ordinary text-key positions.
    names = [{"\n": "Return", "\t": "Tab"}.get(c, "U" + format(ord(c), "04X")) for c in text]
    unique = list(dict.fromkeys(names))
    if not unique or len(unique) > len(TEXT_KEY_SLOTS):
        raise ValueError("Invalid keyboard chunk")
    assignments = dict(zip(TEXT_KEY_SLOTS, unique))
    args = ["wtype"]
    for slot in range(1, TEXT_KEY_SLOTS[len(unique) - 1] + 1):
        args += ["-p", assignments.get(slot, "U" + format(0xE000 + slot, "04X"))]
    for name in names:
        args += ["-k", name]
    return args


class Delivery:
    """Never retry an ambiguous keystroke and never silently use the clipboard."""
    def __init__(self, target, on_failure, run=subprocess.run, focus=active_window,
                 follow_focus=False, stop_event=None, abort_event=None):
        self.target, self.on_failure = target, on_failure
        self.run, self.focus = run, focus
        self.failed = False
        self.delivered = ""
        self.follow_focus = follow_focus
        self.stop_event = stop_event if stop_event is not None else threading.Event()
        self.waiting_for_focus = False
        self.abort_event = abort_event if abort_event is not None else threading.Event()

    def await_focus(self):
        """Keep capture alive through empty workspaces/transient focus queries."""
        while True:
            if self.abort_event.is_set():
                raise RuntimeError("Output cancelled")
            try:
                current = self.focus()
            except (OSError, ValueError, subprocess.SubprocessError):
                current = None
            if current and current.get("address"):
                self.waiting_for_focus = False
                self.target = current
                return
            self.waiting_for_focus = True
            if self.stop_event.wait(0.1):
                raise RuntimeError("No focused window; remaining text saved locally")

    def type_chunk(self, chunk):
        if self.run is not subprocess.run:
            # Injected transports receive the plain text for isolated tests.
            self.run(["wtype", "--", chunk], check=True, capture_output=True, text=True, timeout=30)
        else:
            args = wtype_command(chunk)
            # Monitor a running after-recording delivery. Virtual keyboard events
            # already accepted by the compositor cannot be recalled.
            with subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
                deadline = time.monotonic() + 30
                try:
                    while process.poll() is None:
                        if self.abort_event.is_set() or (not self.follow_focus and self.focus() != self.target):
                            raise RuntimeError("Target window changed during output")
                        if time.monotonic() >= deadline:
                            raise subprocess.TimeoutExpired(args, 30)
                        # Keep the focus-loss window short; already queued
                        # compositor events still cannot be recalled.
                        time.sleep(.005)
                    if process.returncode:
                        raise subprocess.CalledProcessError(process.returncode, args)
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
        if not self.follow_focus and self.focus() != self.target:
            raise RuntimeError("Target window changed during output; delivery is uncertain")

    def send(self, delta):
        if self.failed:
            return False
        try:
            # Short invocations bound focus-change exposure and avoid the old
            # ten-second cutoff on thousands of characters.
            for chunk in delivery_chunks(delta):
                if self.abort_event.is_set():
                    raise RuntimeError("Output cancelled")
                if self.follow_focus:
                    self.await_focus()
                elif self.focus() != self.target:
                    raise RuntimeError("Target window changed")
                self.type_chunk(chunk)
                self.delivered += chunk
            return True
        except Exception as error:
            self.failed = True
            LOG.warning("Output stopped: %s %s", type(error).__name__,
                        getattr(error, "stderr", "") or "")
            self.on_failure("Output stopped; full dictation saved locally")
            return False


class Session:
    def __init__(self, daemon, target):
        self.daemon, self.target = daemon, target
        self.mode = transcription_mode()
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.path = HISTORY / self.id
        self.path.mkdir(mode=0o700)
        self.stop = threading.Event()
        self.abort_output = threading.Event()
        self.error_lock = threading.Lock()
        self.frames = queue.Queue(maxsize=6000)
        self.outputs = queue.Queue()
        self.delivery = Delivery(target, self.fail, follow_focus=self.mode == "live", stop_event=self.stop, abort_event=self.abort_output)
        self.started = time.monotonic()
        self.text = ""
        self.error = ""
        self.peak = 0.0
        self.finished = False
        self.capture = None
        self.thread = threading.Thread(target=self.work, daemon=True)
        self.thread.start()

    def request_stop(self):
        if self.stop.is_set():
            return
        if self.mode == "after":
            try:
                target = active_window()
                if not target.get("address"):
                    raise RuntimeError("No focused target")
                self.delivery.target = target
            except Exception:
                self.fail("No focused window at stop; audio saved locally")
                return
        self.stop.set()

    def fail(self, message):
        with self.error_lock:
            if not self.error:
                self.error = message
                LOG.warning("Session stopped: %s", message)
        self.abort_output.set()
        self.stop.set()

    def emit(self, delta):
        self.text += delta
        atomic(self.path / "transcript.txt", self.text)
        atomic(HISTORY / "latest.txt", self.text)
        if self.mode == "live":
            self.outputs.put(delta)

    def output_loop(self):
        try:
            while (delta := self.outputs.get()) is not None:
                if self.abort_output.is_set():
                    continue
                self.delivery.send(delta)
                atomic(self.path / "delivered.txt", self.delivery.delivered)
        except Exception:
            LOG.exception("Output worker failed")
            self.fail("Could not finish or record output; audio and text retained")

    def capture_worker(self):
        try:
            self.capture_loop()
        except Exception:
            LOG.exception("Capture worker failed")
            self.fail("Capture failed; available audio and text retained")
        finally:
            self.frames.put(None)

    def capture_loop(self):
        """PipeWire owns sample conversion; read 20ms frames without gaps."""
        import numpy as np
        try:
            with (self.path / "capture.log").open("w") as errors, wave.open(str(self.path / "audio.wav"), "wb") as wav:
                wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                self.capture = subprocess.Popen(
                    ["pw-record", "--raw", "--format=s16", "--rate=16000",
                     "--channels=1", "--latency=40ms", "-"],
                    stdout=subprocess.PIPE, stderr=errors,
                )
                pending = b""
                last_audio = time.monotonic()

                def consume(block):
                    nonlocal pending
                    pending += block
                    while len(pending) >= 640:
                        raw, pending = pending[:640], pending[640:]
                        wav.writeframesraw(raw)
                        frame = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
                        self.peak = float(np.max(np.abs(frame)))
                        if self.mode == "after":
                            continue
                        try:
                            self.frames.put_nowait(frame)
                        except queue.Full:
                            self.fail("Recognition is too slow; audio saved locally")

                while not self.stop.is_set():
                    if time.monotonic() - self.started > 7200:
                        self.fail("Two-hour limit reached; finishing dictation")
                        break
                    ready, _, _ = select.select([self.capture.stdout], [], [], 0.1)
                    if not ready:
                        if self.capture.poll() is not None or time.monotonic() - last_audio > 5:
                            raise RuntimeError("Microphone is not providing audio")
                        continue
                    block = os.read(self.capture.stdout.fileno(), 6400)
                    if not block:
                        raise RuntimeError("Microphone capture ended")
                    last_audio = time.monotonic()
                    consume(block)
                # Gracefully flush PipeWire/stdout buffers on F9. Killing the
                # producer without draining its pipe can cut the final syllable.
                self.capture.send_signal(signal.SIGINT)
                drain_deadline = time.monotonic() + 2
                while time.monotonic() < drain_deadline:
                    if select.select([self.capture.stdout], [], [], .1)[0]:
                        block = os.read(self.capture.stdout.fileno(), 6400)
                        if not block:
                            break
                        consume(block)
                if pending:
                    pending = pending[:len(pending) // 2 * 2]
                    wav.writeframesraw(pending)
                    try:
                        if self.mode == "live":
                            self.frames.put_nowait(np.frombuffer(pending, dtype="<i2").astype(np.float32) / 32768)
                    except queue.Full:
                        pass
        except Exception as error:
            LOG.exception("Capture failed")
            self.fail(str(error))
        finally:
            if self.capture is not None:
                self.capture.terminate()
                try:
                    self.capture.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.capture.kill()
                    self.capture.wait()

    def drain_output(self, output, stall_timeout=35):
        """Allow long output while chunks make progress; bound a stalled worker."""
        progress = len(self.delivery.delivered)
        last_progress = time.monotonic()
        while output.is_alive():
            output.join(timeout=.2)
            current = len(self.delivery.delivered)
            if current != progress:
                progress, last_progress = current, time.monotonic()
            if output.is_alive() and time.monotonic() - last_progress >= stall_timeout:
                self.fail("Output stalled; audio and text retained")
                # The transport observes abort_output and kills its child.
                output.join(timeout=3)
                break

    def work(self):
        capture = output = recognizer = None
        try:
            from streaming import OnlineRecognizer
            recognizer = OnlineRecognizer(self.daemon.model, self.emit)
            capture = threading.Thread(target=self.capture_worker, daemon=True)
            output = threading.Thread(target=self.output_loop, daemon=True)
            output.start()
            capture.start()
            broken = False
            while (frame := self.frames.get()) is not None:
                if not broken and not self.abort_output.is_set():
                    try:
                        recognizer.feed(frame)
                    except Exception:
                        LOG.exception("Recognition failed")
                        self.fail("Recognition error; audio and text retained")
                        broken = True
            if self.mode == "after" and not self.error:
                import numpy as np
                with wave.open(str(self.path / "audio.wav")) as audio:
                    while block := audio.readframes(3200):
                        if self.abort_output.is_set():
                            break
                        recognizer.feed(np.frombuffer(block, dtype="<i2").astype(np.float32) / 32768)
            if not broken and not self.abort_output.is_set():
                recognizer.finish()
            if self.mode == "after" and not self.error and self.text:
                self.outputs.put(self.text)
        except Exception:
            LOG.exception("Transcription worker failed")
            self.fail("Could not finish transcription; audio and text retained")
        finally:
            try:
                self.stop.set()
                if capture and capture.ident:
                    capture.join(timeout=6)
                    if capture.is_alive():
                        self.fail("Capture did not finish; audio retained")
                        if self.capture and self.capture.poll() is None:
                            self.capture.kill()
                        capture.join(timeout=3)
                self.outputs.put(None)
                if output and output.ident:
                    self.drain_output(output)
                    if output.is_alive():
                        self.fail("Output did not finish; audio and text retained")
                if self.delivery.delivered != self.text:
                    self.fail("Output is incomplete; full dictation retained")
                result = {
                    "transcription": self.mode,
                    "complete": not self.error and not self.delivery.failed,
                    "error": self.error,
                    "characters": len(self.text),
                    "delivered_characters": len(self.delivery.delivered),
                    "duration_secs": round(time.monotonic() - self.started, 2),
                    "context_recoveries": getattr(recognizer, "context_recoveries", 0),
                }
                # A durable success record is required before deleting audio.
                atomic(self.path / "result.json", json.dumps(result, ensure_ascii=False, indent=2))
                if result["complete"] and not result["context_recoveries"]:
                    (self.path / "audio.wav").unlink(missing_ok=True)
            except Exception:
                LOG.exception("Session finalization failed")
                self.fail("Could not finalize the session; available audio and text retained")
                try:
                    atomic(self.path / "result.json", json.dumps({
                        "complete": False, "error": self.error, "transcription": self.mode,
                        "characters": len(self.text), "delivered_characters": len(self.delivery.delivered),
                    }))
                except Exception:
                    LOG.exception("Could not persist failed session result")
            finally:
                if self.error:
                    try:
                        atomic(HISTORY / "recovery.json", json.dumps({"error": self.error, "session": self.id}))
                    except Exception:
                        LOG.exception("Could not persist recovery notice")
                    try:
                        notify(self.error + ". Open: " + str(self.path))
                    except Exception:
                        LOG.exception("Could not show recovery notification")
                self.finished = True
                LOG.info("Session finished chars=%d delivered=%d error=%s",
                         len(self.text), len(self.delivery.delivered), bool(self.error))


class Daemon:
    def __init__(self):
        self.model = None
        self.model_path = ""
        self.model_error = ""
        self.loading_model = False
        self.model_thread = None
        self.session = None
        self.frontend_token = ""
        self.frontend_seen = 0.0
        self.shutdown = threading.Event()
        self.state_lock = threading.Lock()
        self.write_state("loading")

    def write_state(self, state=None):
        session = self.session
        if state is None:
            state = ("loading" if self.loading_model else ("model-error" if self.model_error else "no-model") if self.model is None else "idle") if session is None or session.finished else (
                ("transcribing" if session.mode == "after" else "finishing") if session.stop.is_set() else "recording")
        data = {"state": state, "model_path": self.model_path, "model_error": self.model_error, "peak": session.peak if state == "recording" else 0,
                "seconds": round(time.monotonic() - session.started) if session else 0,
                "pending": session.frames.qsize() if session and not session.finished else 0,
                "waiting_for_focus": bool(session and not session.finished and session.delivery.waiting_for_focus),
                "session_error": session.error if session else "",
                "recovery": self.recovery(),
                "frontend_available": self.frontend_available()}
        with self.state_lock:
            atomic(ROOT / "state.json", json.dumps(data))
        return data

    def select_model(self, folder, persist=True):
        if self.loading_model or (self.session and not self.session.finished):
            return {"error": "Finish dictation before changing the model."}
        path = model_store.validate(folder)
        self.loading_model = True
        self.model_error = ""
        self.write_state()

        def load():
            try:
                from streaming import load_model
                candidate = load_model(path)
                if persist:
                    model_store.commit(path)
                self.model = candidate
                self.model_path = str(path)
                LOG.info("Model loaded and warmed; ready")
            except Exception:
                LOG.exception("Model could not be loaded")
                self.model_error = "Could not load this model. Select a compatible Parakeet TDT ONNX folder."
            finally:
                self.loading_model = False
                self.write_state()

        self.model_thread = threading.Thread(target=load, daemon=True)
        self.model_thread.start()
        return {"ok": True, "state": "loading"}

    def recovery(self):
        try:
            return json.loads((HISTORY / "recovery.json").read_text())
        except (OSError, ValueError):
            return {}

    def frontend_available(self):
        return bool(self.frontend_token and time.monotonic() - self.frontend_seen < 5)

    def monitor(self):
        while not self.shutdown.wait(0.1):
            try:
                if self.session and not self.session.finished and not self.frontend_available():
                    self.session.fail("Dictation indicator disconnected; audio and text retained")
                self.write_state()
            except Exception:
                LOG.exception("Status monitor failed")
                if self.session and not self.session.finished:
                    self.session.fail("Could not update recording status; audio and text retained")

    def command(self, request):
        action = request.get("action", "status")
        session = self.session
        if action == "frontend":
            token = request.get("token", "")
            if not isinstance(token, str) or not 1 <= len(token) <= 128:
                return {"error": "Invalid frontend token"}
            self.frontend_token, self.frontend_seen = token, time.monotonic()
            return {"ok": True}
        if action == "frontend-stop":
            if request.get("token") == self.frontend_token:
                self.frontend_seen = 0
                if session and not session.finished:
                    session.fail("Dictation indicator closed; audio and text retained")
            return {"ok": True}
        if action == "dismiss-recovery":
            (HISTORY / "recovery.json").unlink(missing_ok=True)
            if session and session.finished:
                session.error = ""
            return self.write_state()
        if action == "model-select":
            return self.select_model(request.get("path", ""))
        if action == "status":
            return self.write_state()
        if action == "stop":
            if session and not session.finished:
                session.request_stop()
            return self.write_state()
        if action != "toggle":
            return {"error": "Unknown command"}
        if session and not session.finished:
            if not session.stop.is_set():
                session.request_stop()
            return self.write_state()
        if self.loading_model or self.model is None:
            return {"error": "Choose a model in Dictation settings and wait until Ready."}
        if not self.frontend_available():
            return {"error": "Enable the Dictation plugin before recording."}
        target = active_window()
        if not target.get("address"):
            return {"error": "No active target window"}
        self.session = Session(self, target)
        return self.write_state()

    def serve(self):
        try:
            initial_model = model_store.selected()
            if initial_model:
                self.select_model(initial_model, persist=False)
        except (OSError, ValueError):
            self.model_error = "Saved model is unavailable. Choose a model in settings."
        endpoint = ROOT / "control.sock"
        endpoint.unlink(missing_ok=True)
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(endpoint))
            os.chmod(endpoint, 0o600)
            server.listen(4)
            server.settimeout(0.5)
            monitor = threading.Thread(target=self.monitor, daemon=True)
            monitor.start()
            self.write_state()
            while not self.shutdown.is_set():
                try:
                    connection, _ = server.accept()
                except socket.timeout:
                    continue
                with connection:
                    connection.settimeout(2)
                    try:
                        request = json.loads(connection.recv(4096))
                        response = self.command(request)
                        connection.sendall(json.dumps(response).encode())
                    except Exception as error:
                        LOG.exception("Command failed")
                        try:
                            connection.sendall(json.dumps({"error": str(error)}).encode())
                        except OSError:
                            pass
        if self.session and not self.session.finished:
            self.session.fail("Dictation service stopped; audio and text retained")
            self.session.thread.join(timeout=60)
        monitor.join(timeout=2)
        endpoint.unlink(missing_ok=True)
        self.write_state("stopped")


def client(action):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(4)
        connection.connect(str(ROOT / "control.sock"))
        connection.sendall(json.dumps({"action": action}).encode())
        response = json.loads(connection.recv(4096))
    if response.get("error"):
        raise RuntimeError(response["error"])
    return response


def main():
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, exist_ok=True)
    HISTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["serve", "toggle", "stop", "status", "copy-last"], default="toggle", nargs="?")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.action == "serve":
        with (ROOT / "daemon.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            daemon = Daemon()
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, lambda *_: daemon.shutdown.set())
            daemon.serve()
    elif args.action == "copy-last":
        subprocess.run(["wl-copy"], input=(HISTORY / "latest.txt").read_text(),
                       text=True, check=True, timeout=5)
        notify("Latest dictation copied")
    else:
        try:
            print(json.dumps(client(args.action)))
        except Exception as error:
            notify("Dictation service is not ready: " + str(error))
            raise SystemExit(1) from error


if __name__ == "__main__":
    main()
