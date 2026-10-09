# Dictation user guide

Local speech-to-text into the focused text field. Choose **Live** for incremental
text while speaking or **After recording** for insertion after you stop.
The native microphone panel controls the model, shortcut and recording overlay.

Status: preview release, not yet listed in the plugin marketplace. See [release checks](RELEASE_CHECKLIST.md)
for completed tests and remaining checks.

## Requirements

Currently targeted: Linux x86_64, Omarchy Quattro with Lua Hyprland bindings,
PipeWire and a working microphone. Run setup with Omarchy’s system `python3`;
`uv` installs a separate Python 3.12 environment for speech recognition if needed.
The tested desktop baseline is
Omarchy 4.0.4, Hyprland 0.56.2 and Quickshell 0.3.1. Other releases are not yet
claimed as supported.

Required commands: `git`, `python3`, `uv`, `pw-record`, `wtype`, `hyprctl`, `omarchy`,
`omarchy-shell`, `systemctl`, `wl-copy`, `xdg-open`, and `luac`.
On Arch these additional tools are supplied by `uv`, `pipewire`, `wtype`,
`wl-clipboard`, `xdg-utils`, and `lua`. Setup checks availability and does not run
sudo or silently install system packages. Use your normal package manager for
missing packages.

## Install

In a terminal in your logged-in Omarchy desktop session:

```sh
git clone https://github.com/DomeMcFly/omarchy-dictation.git
cd omarchy-dictation
python3 setup.py check
python3 setup.py install
```

While this repository is private, cloning requires GitHub access to it.

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

Click the microphone icon in the Omarchy bar to open settings. Click outside, press Escape or click the
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
| Service unavailable / Service stopped | Choose **Start service** in the panel. |
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
makes the indicator react to microphone level and adds a gentle breathing
motion to the circle. Turning it off stops both animations. Preview uses simulated
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
Download size is approximately 2.55 GB. Downloaded files are checked before use.
A new model must load successfully before the selection is saved; if loading
fails, the previous model remains selected. See [third-party notices](../THIRD_PARTY_NOTICES.md).

Use **Add model… → Use model folder…** for another compatible local export.
Existing compatible folders in `~/.local/share/voxtype/models` are discovered
for migration, but never required or deleted.


## Focus and delivery limitations

After changing tabs, windows or workspaces, select an editable field before
continuing. The overlay indicates activity and screen focus, not text-field
readiness. Virtual keyboard input outside a text field can trigger app actions.

Keep the intended text field selected until all text has appeared. In Live mode,
pending words can appear in a window you switch to. With no focused window,
Dictation waits until focus returns or you stop.

After-recording mode inserts into the window focused when you stop recording.
It stops insertion if it detects a window change, but some text may still reach
the new field. Changes between fields in the same window cannot be detected.
Always check the inserted text. Failed or uncertain output is saved for recovery
and is not automatically inserted again.

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
Audio is deleted after successful dictation. Failed or uncertain sessions retain
audio for recovery; audio is also retained when recognition had to recover during
a long recording. Saved transcripts are not deleted automatically.

### Delete saved dictations

Finish recording and wait for text insertion to complete first. Open
`~/.local/state/voice-dictation/` in your file manager (or
`$XDG_STATE_HOME/voice-dictation/` if you customized that location).

Each dictation has a dated folder such as `20261009-221800-a1b2c3`. Delete the
folders for dictations you no longer need. To also remove the separate copy of
the latest transcript, delete `latest.txt`. If you delete a dictation offered for
recovery, dismiss its recovery notice in the panel.

Keep `installation.json`, `setup.lock` and `backups/`: these belong to installation
and removal, not dictation history. Do not delete the entire parent folder.

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

If you installed using the clone command above, open that source directory,
run `git pull --ff-only`, then `python3 setup.py update` and
`omarchy restart shell`. Finish recording before updating. Models, settings
and history remain intact.

For an Omarchy-installed plugin, uninstall **before** removing the plugin checkout:

```sh
python3 ~/.config/omarchy/plugins/dominic.live-dictation/setup.py uninstall
omarchy plugin remove dominic.live-dictation
```

For the clone-and-setup installation, run `python3 setup.py uninstall` from
the source directory before deleting it.

Uninstall removes the managed shortcut block, disables/removes the service and
launcher, and removes unmodified installer-owned files. Files modified outside
setup are preserved and reported. Models, preferences, dictations and backups
are retained. An unrelated original keybinding becomes active again on reload.

## Further information

See [testing and development](TESTING.md) and the [release checklist](RELEASE_CHECKLIST.md).
Application code: [MIT](../LICENSE). Models and third-party code have their own
[license notices](../THIRD_PARTY_NOTICES.md).
