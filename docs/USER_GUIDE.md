# Dictation user guide

Local speech-to-text into the focused text field. Choose **Live** for incremental
text while speaking or **After recording** for insertion after you stop.
The native microphone panel controls the model, shortcut and recording overlay.

Status: preview release, not yet listed in the plugin marketplace. See [release checks](RELEASE_CHECKLIST.md)
for the distinction between automated coverage and outstanding desktop acceptance.

## Requirements

Currently targeted: Linux x86_64, Omarchy Quattro with Lua Hyprland bindings,
Python 3.12, PipeWire and a working microphone. The tested desktop baseline is
Omarchy 4.0.4, Hyprland 0.56.2 and Quickshell 0.3.1. Other releases are not yet
claimed as supported.

Required commands: `uv`, `pw-record`, `wtype`, `hyprctl`, `omarchy`,
`omarchy-shell`, `systemctl`, `wl-copy`, `xdg-open`, and `luac`.
On Arch these additional tools are supplied by `uv`, `pipewire`, `wtype`,
`wl-clipboard`, `xdg-utils`, and `lua`. Setup checks availability and does not run
sudo or silently install system packages. Use your normal package manager for
missing packages.

## Install

Run from a checkout in your logged-in Omarchy desktop session:

```sh
python3 setup.py check
python3 setup.py install
```

Setup creates a dedicated Python environment, installs the pinned CPU runtime,
installs and enables the user service, creates `~/.local/bin/live-dictation`,
and enables the native plugin. `uv` may download Python 3.12 and dependencies.
The model is downloaded only when you explicitly choose **Download recommended**
in the panel. No account or cloud transcription service is needed.

If installed using `omarchy plugin add <repository-url>`, run the same setup
command from `~/.config/omarchy/plugins/dominic.live-dictation/`. Omarchy only
installs plugin files; the setup command installs the speech recognition service.

### Shortcut conflicts

Setup attempts F9 only if it is free or already owned by this application.
A conflict leaves the existing binding intact; choose an unused shortcut in the
panel or pass `--shortcut 'SUPER + CTRL + D'` (also checked for conflicts).

Omarchy may already assign a shortcut to Voxtype, its existing dictation tool.
To intentionally replace that stock shortcut with Dictation:

```sh
python3 setup.py install --shortcut F9 --replace-voxtype
```

This checks for the expected stock binding and replaces only the requested key.
It does not disable Voxtype's service or remove its other shortcuts. Custom
bindings are rejected rather than silently replaced. Do not run two recorders
at once. Changing or removing this application's override allows the original
Omarchy default to take effect again. The global shortcut overview lists
**Dictation: start/stop**.

## Use

Focus a text field and press the configured shortcut to start, then press it
again to finish. No Enter key is sent. The application does not automatically
change the clipboard.

Click the microphone to open settings. Click outside, press Escape or click the
microphone again to dismiss. Opening settings finishes an active dictation first.
Appearance settings save immediately; shortcut changes use **Apply**.
**Preview** displays a simulated indicator without recording.

- **Dictation:** compatible model, live/after-recording mode, global shortcut.
- **Overlay:** visibility, waveform/compact/circle, position, screen, margin,
  size and opacity. These controls remain visible but disabled when overlay is off.
- **Indicators:** microphone highlight, status text and audio-level animation.
  Turning off the overlay still highlights the microphone while recording.

The default screen setting, **Follow active screen**, moves the recording overlay
with the focused monitor throughout recording and output. Workspace changes on
the same monitor keep the overlay visible. Selecting a named screen pins the
overlay there; if that screen disconnects, it falls back to the active screen.


Errors reveal contextual **Start service**, **Copy latest**, **Open dictations**
and **Dismiss** actions. These actions do not clutter the normal view. A copy
operation is explicit; pasting an entire recovered transcript can duplicate text
already inserted, so inspect it first.

### Status and indicators

**Ready** means the speech service has prepared the selected model, the
microphone indicator is connected, and a shortcut is set. Select a text field
and use the shortcut to begin. The microphone is opened only when recording
starts; Ready does not check the microphone or whether a field accepts text.
Shortcuts are checked when saved in the panel. If you edit Omarchy keybindings
elsewhere, check for conflicts there too.

| Status | Meaning / next action |
| --- | --- |
| No model installed | No compatible model is available; download or add one. |
| Choose a model | Compatible folders exist but none is loaded; select one. |
| Loading model… | Preparing the speech model; wait. |
| Model unavailable | The saved model is missing, invalid or failed to load; see the error below Model. |
| Set a shortcut / Check shortcut | Configure a shortcut or resolve the displayed shortcut error. |
| Connecting… | Waiting for the speech service to connect to the panel. |
| Service unavailable / Service stopped | Start the backend using the contextual action. |
| Recording | Microphone session is active. |
| Finishing… / Transcribing… | Recording has stopped; remaining recognition/output is being completed. |

If switching to another model fails, an already loaded model remains usable;
the status may return to Ready while the failed switch is explained below Model.
An error from an earlier dictation stays visible until dismissed, even when
you can start a new recording.

The bar microphone opens settings. Its underline marks the open panel, matching
Omarchy's other widgets. **Highlight microphone** colors it during recording.
With the overlay disabled, a red recording indicator is mandatory and that
toggle is shown checked and disabled. **Show overlay status** adds Recording,
Finishing, Transcribing or Preview to every overlay style. **Animate overlay**
makes the waveform/circle react to microphone level; off keeps the indicator
static. The circle also has a gentle breathing motion. Preview uses simulated
levels and never opens the microphone. The larger microphone beside the panel
title identifies the app and is not a separate record button.

## Models

The current engine supports **Parakeet TDT 0.6B v3 ONNX**, CPU, full-precision
export with config.json, vocab.txt, encoder-model.onnx,
encoder-model.onnx.data and decoder_joint-model.onnx. Arbitrary Whisper models
and quantized exports are not interchangeable with this engine.

The recommended model is NVIDIA Parakeet, converted to ONNX by Ivan Stupakov:
[model source](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx),
[CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/).
Download size is approximately 2.55 GB. The pinned revision and every file's
integrity are checked before the download becomes selectable. Switching models
warms the candidate before persisting the selection; a failed load keeps the
previous model. See [third-party notices](../THIRD_PARTY_NOTICES.md).

Use **Add model… → Use model folder…** for another compatible local export.
Existing compatible folders in `~/.local/share/voxtype/models` are discovered
for migration, but never required or deleted.


## Focus and delivery limitations

After changing tabs, windows or workspaces, select an editable field before
continuing. The overlay indicates activity and screen focus, not text-field
readiness. Virtual keyboard input outside a text field can trigger app actions.

Live mode follows the currently focused window, including pending words spoken
before a focus change. With no focused window, it waits until focus returns or
you stop. After-recording mode captures the target window when you stop and
checks it before, during and after each output process. A detected focus change
kills the running output and retains recovery data.

Output uses a Wayland virtual keyboard, not a text-field API. Focus checking and
keyboard delivery are not atomic. Characters already queued in the compositor
can still reach a different field or window; switching fields inside the same
window is not detectable. The application cannot guarantee delivery to a
particular text field. Keep focus stable through completion, especially for
sensitive text. A successful result means the keyboard process completed, not
that an application acknowledged every character. Failed or ambiguous output is
never retried automatically.

## Files, privacy and lifecycle

- Plugin: `$XDG_CONFIG_HOME/omarchy/plugins/dominic.live-dictation/`.
- Settings and model selection: `$XDG_CONFIG_HOME/voice-dictation/`.
- Backend environment and code: `$XDG_DATA_HOME/voice-dictation/runtime/`.
- Downloaded models: `$XDG_DATA_HOME/voice-dictation/models/`.
- Service: `$XDG_CONFIG_HOME/systemd/user/voice-dictation.service`.
- History and setup backups: `$XDG_STATE_HOME/voice-dictation/`.
- Socket/status: `$XDG_RUNTIME_DIR/voice-dictation/`.

XDG variables fall back to the standard directories under your home. Files are
private to your user. Transcripts are stored locally until you delete them.
Audio from successful sessions is deleted only after a successful completion
record is written. Failed, uncertain or context-recovery sessions retain audio.
Backups and history are excluded from release exports. No retention timer is
currently implemented. Delete history only while no recording is running.

The independent service keeps the model warm. Recording requires a connected
plugin indicator. Disabling/removing the plugin or closing the shell cancels
an active session; a missed disconnect is detected within five seconds. Audio
and text are retained on cancellation. Re-enabling does not resume recording.
The shortcut remains registered until uninstall but cannot record without the
plugin. Shell reloads can cancel a session; finish recording before reloading.

## Update and uninstall

For a git-installed plugin:

```sh
omarchy plugin update dominic.live-dictation
python3 ~/.config/omarchy/plugins/dominic.live-dictation/setup.py update
omarchy restart shell
```

For a development checkout, pull the desired revision and run `python3 setup.py
update` there. Finish recording first. Update refreshes backend dependencies and
code as well as the UI. Restart the shell after updating: on the tested
Quickshell version a plugin rescan can retain cached QML components. Models,
settings and history remain intact.

Run uninstall **before** removing the plugin checkout:

```sh
python3 ~/.config/omarchy/plugins/dominic.live-dictation/setup.py uninstall
omarchy plugin remove dominic.live-dictation
```

Uninstall removes the managed shortcut block, disables/removes the service and
launcher, and removes unmodified installer-owned files. Files modified outside
setup are preserved and reported. Models, preferences, dictations and backups
are retained. An unrelated original keybinding becomes active again on reload.

## Further information

See [testing and development](TESTING.md) and the [release checklist](RELEASE_CHECKLIST.md).
Application code: [MIT](../LICENSE). Models and third-party code have their own
[license notices](../THIRD_PARTY_NOTICES.md).
