# Dictation for Omarchy

Turn your voice into text in your focused app. Dictation brings local speech
recognition to Omarchy, with live text insertion or transcription after recording.
Start and stop with one shortcut, and customize the recording indicator from a
native microphone panel. No account or cloud transcription service required.

![Dictation settings and waveform preview in Omarchy](preview.png)

*Native settings panel with a simulated waveform preview. No microphone is used
for preview. The screenshot predates the screen option rename to **Follow active
screen**.*

### Settings at a glance

| Area | Controls | What they do |
| --- | --- | --- |
| Dictation | Model | Select a compatible local speech model or download the recommended one. |
| Dictation | Transcription | Choose incremental **Live** output or insertion **After recording**. |
| Dictation | Shortcut · Apply | Set the global start/stop shortcut; Apply saves it after validation. |
| Overlay | Show overlay · Style | Show a waveform, compact indicator or pulsing circle while dictating. |
| Overlay | Position · Screen | Place the indicator; **Follow active screen** follows monitor focus, or choose a fixed screen. |
| Overlay | Margin · Size · Opacity | Adjust edge spacing, scale and transparency. |
| Indicators | Highlight microphone | Color the bar microphone during recording; required when the overlay is hidden. |
| Indicators | Show overlay status | Add a short status label to the recording indicator. |
| Indicators | Animate overlay | Make the indicator react to audio levels. |
| Panel | Preview | Try the appearance with simulated audio levels, without recording. |
| Panel | Reset appearance | Restore display defaults without changing the model, shortcut or transcription mode. |

## What it does

- **Live:** inserts text incrementally while you speak.
- **After recording:** transcribes and inserts text after you stop.
- **One configurable shortcut:** starts and stops dictation from other apps.
- **Local recognition:** no account or cloud transcription service.
- **Your preferred indicator:** waveform, compact or pulsing circle, with
  position, screen, size, opacity and animation controls.
- **Model setup in the panel:** download the recommended compatible model or
  select a compatible local folder.
- **Recovery when something fails:** retains incomplete dictations and offers
  contextual recovery actions.

## Current status

**0.2.0 — release candidate, not yet published.** Local acceptance includes real
keyboard delivery into an editor, browser and terminal, installation lifecycle
checks, model download verification, 66 Python tests and 27 QML checks.

A fresh Omarchy installation and broader natural-speech testing remain open.
See the [release checklist](docs/RELEASE_CHECKLIST.md) for evidence and limitations.

## Install

Tested on **Omarchy 4.0.4, Hyprland 0.56.2 and Quickshell 0.3.1**, Linux x86_64.
Requires Python 3.12, PipeWire, a microphone and the desktop tools listed in the
[user guide](docs/USER_GUIDE.md#requirements). Voxtype is not required.

From the downloaded source directory, in your logged-in Omarchy session:

```sh
python3 setup.py check
python3 setup.py install
```

Setup checks system dependencies, creates a dedicated Python environment and
installs the backend service and native plugin. It may download Python and
Python packages, but does not install system packages automatically.

Open the microphone panel and choose **Download recommended** to fetch the
approximately 2.55 GB Parakeet ONNX model, or select an existing compatible model.
The current engine supports Parakeet TDT 0.6B v3 ONNX; arbitrary speech models are
not interchangeable. Downloading a model is an explicit action.

F9 is used only when available. If it conflicts, choose an unused shortcut in
the panel. For intentional migration from the stock Voxtype shortcut, see
[shortcut conflicts](docs/USER_GUIDE.md#shortcut-conflicts).

Installing the frontend through Omarchy alone does not set up the backend;
[the setup command is still required](docs/USER_GUIDE.md#install).

## Use

1. Choose **Live** or **After recording** in the microphone panel.
2. Close the panel by clicking outside or clicking the microphone again.
3. Focus a text field and press your shortcut to start speaking.
4. Press the shortcut again to stop; wait for remaining text to finish.

**Ready** means the model is loaded and warmed, the plugin is connected and a
shortcut is configured. It does not test the microphone or the target text field.
**Preview** lets you adjust the overlay without recording.

## Important limits and privacy

Recognition runs locally. Text is inserted without sending Enter or automatically
changing the clipboard. Transcripts are kept locally until deleted; failed or
uncertain sessions also retain audio. There is currently no automatic retention
limit. See [storage and lifecycle](docs/USER_GUIDE.md#files-privacy-and-lifecycle).

Keep focus stable while text is being inserted. Live mode follows the focused
window, including pending words. After-recording output stops on a detected
window change, but queued characters can still reach the next field. Tests
observed one character after a focus switch; this is not a guaranteed maximum.
Switching fields within the same window cannot be detected. The overlay follows
the active screen but cannot tell whether a text field is selected. Select an
editable field after switching tabs, windows or workspaces before continuing;
virtual keyboard input outside a text field may trigger application actions.

Punctuation comes from the recognition model and may interpret pauses as sentence
boundaries. Recognition accuracy and speed depend on speech and hardware.

## Update or remove

Finish any recording first. From the source directory after obtaining the new
version:

```sh
python3 setup.py update
omarchy restart shell
```

To uninstall, run this before deleting the source directory:

```sh
python3 setup.py uninstall
```

Models, settings and dictation history are retained. For plugins installed via
Omarchy's repository workflow, follow the additional
[update and removal steps](docs/USER_GUIDE.md#update-and-uninstall).

## Documentation and license

- [User guide](docs/USER_GUIDE.md): model support, statuses, shortcuts and storage.
- [Tests](docs/TESTING.md) and [release checklist](docs/RELEASE_CHECKLIST.md).
- [MIT license](LICENSE) and [third-party/model notices](THIRD_PARTY_NOTICES.md).

Publication uses an explicit export:

```sh
python3 setup.py export --output /path/to/new-release-directory
```

The export includes source, tests, documentation and
licenses, excluding personal settings, recordings, models and development notes.

## Repository layout

- `omarchy-plugin/`: native QML frontend and its control helpers.
- `dictation.py`, `streaming.py`, `model_store.py`: backend and model handling.
- `docs/`: user guide, release checks and testing documentation.
- `preview.png`: the screenshot shown above.
- `tests/`: automated Python and QML tests.
- `tools/`: manual development probes, excluded from the release export.
- `setup.py` and `manifest.json`: installation and Omarchy plugin entry points.

The root backend modules are deliberately kept beside the installer; this small
project does not need a separate Python package layout. Historical work notes
and private validation logs are stored outside the repository.
