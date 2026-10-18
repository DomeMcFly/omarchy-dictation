"""Exercise real wtype on a private Wayland receiver, never the user desktop."""
import array
from collections import deque
import ctypes
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from dictation import Delivery


def message(object_id, opcode, body=b''):
    return struct.pack('II', object_id, ((8 + len(body)) << 16) | opcode) + body


def string(value):
    data = value.encode() + b'\0'
    return struct.pack('I', len(data)) + data + b'\0' * (-len(data) % 4)


class KeyboardReceiver:
    """Minimal server for the registry, seat and virtual-keyboard protocols."""
    def __enter__(self):
        self.directory = tempfile.TemporaryDirectory(prefix='dictation-wayland-')
        self.path = str(Path(self.directory.name) / 'wayland-test')
        self.server = socket.socket(socket.AF_UNIX)
        self.server.bind(self.path)
        self.server.listen()
        self.server.settimeout(.1)
        self.stopped = threading.Event()
        self.presses = []
        self.first_key_events = []
        self.errors = []
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stopped.set()
        self.thread.join(timeout=3)
        self.server.close()
        self.directory.cleanup()

    def serve(self):
        while not self.stopped.is_set():
            try:
                connection, _ = self.server.accept()
            except socket.timeout:
                continue
            try:
                with connection:
                    self.receive(connection)
            except Exception as error:
                self.errors.append(error)

    def receive(self, connection):
        objects, keymaps, started_keyboards = {1: 'display'}, {}, set()
        data, descriptors = bytearray(), deque()
        try:
            while True:
                incoming, ancillary, _, _ = connection.recvmsg(65536, socket.CMSG_SPACE(16 * 4))
                if not incoming:
                    return
                data.extend(incoming)
                for level, kind, payload in ancillary:
                    if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                        fds = array.array('i')
                        fds.frombytes(payload[:len(payload) - len(payload) % fds.itemsize])
                        descriptors.extend(fds)
                while len(data) >= 8:
                    object_id, header = struct.unpack_from('II', data)
                    size, opcode = header >> 16, header & 0xffff
                    if len(data) < size:
                        break
                    body = bytes(data[8:size])
                    del data[:size]
                    interface = objects[object_id]
                    if interface == 'display' and opcode == 1:
                        registry, = struct.unpack('I', body)
                        objects[registry] = 'registry'
                        for name, iface, version in ((1, 'wl_seat', 7), (2, 'zwp_virtual_keyboard_manager_v1', 1)):
                            connection.sendall(message(registry, 0, struct.pack('I', name) + string(iface) + struct.pack('I', version)))
                    elif interface == 'display' and opcode == 0:
                        callback, = struct.unpack('I', body)
                        connection.sendall(message(callback, 0, struct.pack('I', 0)) + message(1, 1, struct.pack('I', callback)))
                    elif interface == 'registry' and opcode == 0:
                        name, = struct.unpack_from('I', body)
                        new_id, = struct.unpack_from('I', body, len(body) - 4)
                        objects[new_id] = 'seat' if name == 1 else 'manager'
                        if name == 1:
                            connection.sendall(message(new_id, 0, struct.pack('I', 2)))
                    elif interface == 'manager' and opcode == 0:
                        _, keyboard = struct.unpack('II', body)
                        objects[keyboard] = 'keyboard'
                    elif interface == 'keyboard' and opcode == 0:
                        _, length = struct.unpack('II', body)
                        fd = descriptors.popleft()
                        try:
                            raw = os.pread(fd, length, 0).decode()
                        finally:
                            os.close(fd)
                        keymaps[object_id] = {int(code): symbol for code, symbol in re.findall(r'key <K(\d+)> \{\[([^\]]+)\]\};', raw)}
                    elif interface == 'keyboard' and opcode == 1:
                        _, code, state = struct.unpack('III', body)
                        if object_id not in started_keyboards:
                            self.first_key_events.append((code, state))
                            started_keyboards.add(object_id)
                        if state == 1:
                            self.presses.append((code, keymaps[object_id][code]))
        finally:
            for fd in descriptors:
                os.close(fd)


@unittest.skipUnless(shutil.which('wtype'), 'requires the production wtype binary')
class WtypeTransportTests(unittest.TestCase):
    def test_real_delivery_uses_printable_physical_keys_and_preserves_unicode(self):
        target = {'address': 'isolated-test', 'pid': 1}
        text = 'a' * 125 + 'Diktat: Grüße, Straße, Äpfel 123!? € @ + / () ' * 3
        xkb = ctypes.CDLL('libxkbcommon.so.0')
        xkb.xkb_keysym_from_name.argtypes = [ctypes.c_char_p, ctypes.c_int]
        xkb.xkb_keysym_from_name.restype = ctypes.c_uint32
        xkb.xkb_keysym_to_utf32.argtypes = [ctypes.c_uint32]
        xkb.xkb_keysym_to_utf32.restype = ctypes.c_uint32
        with KeyboardReceiver() as receiver:
            environment = os.environ.copy()
            environment.pop('WAYLAND_SOCKET', None)
            environment['WAYLAND_DISPLAY'] = receiver.path
            real_popen = subprocess.Popen
            observed_arguments = []
            def observe_process(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                # stdin stays open while we observe the real child. No dictated
                # characters or encodings may appear in its procfs command line.
                deadline = time.monotonic() + 2
                while True:
                    raw = Path(f'/proc/{process.pid}/cmdline').read_bytes()
                    if raw.split(b'\0')[0].endswith(b'wtype'):
                        observed_arguments.append(raw)
                        return process
                    if time.monotonic() >= deadline:
                        process.kill(); process.wait()
                        raise AssertionError('Could not observe the wtype process')
                    time.sleep(.001)
            with patch.dict(os.environ, environment, clear=True), \
                    patch('dictation.subprocess.Popen', side_effect=observe_process):
                for follow_focus in (True, False):
                    failures = []
                    delivery = Delivery(target, failures.append, focus=lambda: target, follow_focus=follow_focus)
                    self.assertTrue(delivery.send(text), failures)
            self.assertEqual(receiver.errors, [])
            self.assertTrue(observed_arguments)
            self.assertTrue(all(raw == b'wtype\0-\0-p\0UE001\0' for raw in observed_arguments))
            self.assertTrue(receiver.presses)
            # Upload the text keymap before the first key event. Releasing the
            # reservation first causes real GTK clients to miss stdin output.
            self.assertTrue(all(state == 1 for _, state in receiver.first_key_events))
            # Linux evdev 2..13 are the printable number row. Function,
            # modifier, lock and navigation positions must never be pressed.
            self.assertTrue(all(2 <= code <= 13 for code, _ in receiver.presses),
                            sorted({code for code, _ in receiver.presses}))
            received = ''.join(chr(xkb.xkb_keysym_to_utf32(xkb.xkb_keysym_from_name(symbol.encode(), 0)))
                               for _, symbol in receiver.presses)
            self.assertEqual(received, text * 2)
