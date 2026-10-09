# Native frontend

The application manifest and installer are in the repository root. See the
[root README](../README.md) for installation, models, usage and lifecycle.

This directory holds the bar widget, native settings panel, recording overlay,
local persistence/controller helper and managed shortcut integration. The model
store is shared with the backend from `../model_store.py` without symlinks.

`SettingsDropdown.qml` adapts Omarchy's dropdown to close when its trigger is
clicked again. Its license notice is in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
