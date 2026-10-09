# Validation

From the repository or an exported release, create/use a Python 3.12 environment
with `requirements.lock` and run:

```sh
python -m unittest discover -p 'test_*.py' -v
QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME=generic QT_QUICK_CONTROLS_STYLE=Basic \
  /usr/lib/qt6/bin/qmltestrunner -input tests/qml -import tests/qml
python setup.py export --output /tmp/live-dictation-release
omarchy plugin validate /tmp/live-dictation-release
```

The Python suite covers streaming agreement, Unicode, focus changes, delivery
failures, live/after-recording separation, model validation/download integrity,
shortcut ownership and installation lifecycle. Temporary directories and mocked
OS commands isolate destructive/failure scenarios. Tests never record a real
microphone, type into user windows or change real keybindings.

QML tests exercise the production dropdown with lightweight theme fixtures.
They do not establish that every native panel/lifecycle path is correct.

See [release checks](RELEASE_CHECKLIST.md) for real desktop acceptance and remaining limitations.

## Source layout and release export

- `omarchy-plugin/`: QML panel, bar widget, overlay and control helpers.
- `dictation.py`, `streaming.py`, `model_store.py`: recognition, delivery and models.
- `tests/`: automated Python and QML checks.
- `docs/`: user guide, test instructions and release checklist.
- `manifest.json`, `setup.py`: plugin metadata and installation.
- `preview.png`: repository and marketplace preview.

Create a clean release directory with:

```sh
python3 setup.py export --output /path/to/new-release-directory
```

The export includes source, tests, documentation and licenses. It excludes local
environments, models, recordings, backups and internal development notes.
The development workspace may also contain manual probes under `tools/`; those
are not part of the release. The export command does not upload anything.
