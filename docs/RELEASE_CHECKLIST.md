# Release acceptance — 2026-10-09

Status: release candidate. The automated/local acceptance below is complete;
a fresh operating-system session and structured natural microphone acceptance remain open.
Nothing has been published.

## Completed on the local baseline

- [x] 66 Python regression tests, including disk-write failures, cancellation,
      progress-aware output draining, model states, shortcut ownership and setup.
- [x] 27 QML checks, including dropdown interaction and status presentation.
- [x] Clean release export, root manifest, no private backups or symlinks;
      tests also executed from the export.
- [x] Actual local uninstall/reinstall with real systemd and Omarchy commands:
      service, launcher and managed plugin removed/recreated, preferences and
      unrelated shortcut text preserved. Independent dependency environment rebuilt.
- [x] Actual pinned model download into an empty, separate XDG model store:
      integrity verification, inference warmup and persisted selection succeeded
      without an existing Voxtype model (approximately 381 seconds).
- [x] Three disable/enable cycles with the panel open; two supervised shell
      restarts and one standard `omarchy restart shell`, also with panel open.
      One shell remained; the panel/heartbeat recovered; no new coredump found.
- [x] Backend startup without a model and with malformed model settings remained
      responsive and rejected recording. Explicit model selection repairs malformed
      settings after backing them up.
- [x] Contextual service-start action and healthy panel layout verified locally.
- [x] Recovery text copied exactly into the isolated Wayland clipboard; the
      helper returns its JSON success response while the clipboard owner lives.

## Real audio and keyboard transport

These tests used a separate nested Hyprland compositor, a private PipeWire
instance with a policy-only WirePlumber, and synthetic German speech. They used
real `pw-record`, the actual Parakeet/ONNX model and production `wtype` delivery.
The applications were a GTK TextView editor, Chromium textarea and foot terminal.
No physical microphone was used. These are not natural-speech quality results.

| Target | Live | After recording |
| --- | --- | --- |
| GTK editor | 302/302 characters, exact | 302/302 characters, exact |
| Chromium | 302/302 characters, exact | 302/302 characters, exact |
| Terminal | 302/302 characters, exact | 302/302 characters, exact |

Live first text arrived in 2.81–2.91 seconds in this fixture. After-recording
mode produced no text before stop. A 70.93-second fixture in after-recording
mode delivered all 1,211 recognized characters in 124.12 seconds total.
Separate long Unicode delivery into a terminal delivered 3,835/3,835 characters
exactly in 20.67 seconds. These timings are specific to this test machine.

Disconnecting the PipeWire source and disconnecting the frontend each finished
the session with complete=false, retained audio and a recovery record. Live
output followed two test windows within one delivery session without losing text.

## Known focus limitation — confirmed, not eliminated

After-recording output stops when window focus changes. The initial test still
sent three queued characters into the second test window. Reducing focus polling
from 20 ms to 5 ms reduced this to one character in each of three repeat tests.
This is not a zero-leak guarantee: virtual-keyboard input and compositor focus
are not atomic, and same-window text-field changes cannot be detected. Keep focus
stable until insertion finishes. Failed output is marked uncertain and retained.

## Fixes found during acceptance

- Uninstall now removes empty managed plugin directories and derived bytecode,
  allowing reinstall; unrelated files remain intact.
- Output draining now measures stalled progress rather than imposing a 35-second
  total cutoff, so long output can finish while still detecting a stuck worker.
- The long receiver fixture allows enough time on a slower nested compositor.
- Update instructions explicitly restart the shell because plugin rescans on the
  tested Quickshell version can retain cached QML components.
- Clipboard recovery detaches the clipboard owner's output streams so that
  the panel receives completion immediately instead of waiting for ownership to end.

## Still open before a stable tag

- [ ] Install on a fresh Omarchy system without the developer's existing
      configuration; log out/in and check startup, then update/uninstall/reinstall.
- [ ] Natural speech through a physical microphone in the three target apps,
      including realistic noise, pauses, long speech and hardware reconnection.
- [ ] Decide whether the documented focus limitation is acceptable for the release;
      strict text-field isolation would require a different delivery mechanism.

An earlier Quickshell teardown crash was observed before this acceptance run.
It has not recurred here and is not proven to originate in this plugin. Its root
cause is still unresolved; successful cycles do not establish a root-cause fix.

Tested baseline: Omarchy 4.0.4, Hyprland 0.56.2, Quickshell 0.3.1, Python 3.12,
Linux x86_64 CPU. Other versions are not claimed as supported.

Detailed logs, test harnesses and reports are stored privately outside the source
and release tree under the user's voice-dictation state directory:
`validation/acceptance-20261009/`.
