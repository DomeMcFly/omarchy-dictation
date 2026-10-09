import QtQuick
import QtTest
import "../../omarchy-plugin/Status.js" as Status

TestCase {
    name: "DictationStatus"
    function test_states_data() {
        return [
            {tag: "empty installation", phase: "no-model", models: 0, expected: "No model installed"},
            {tag: "available but not selected", phase: "no-model", models: 2, expected: "Choose a model"},
            {tag: "failed model load", phase: "model-error", expected: "Model unavailable"},
            {tag: "loading is not ready", phase: "loading", expected: "Loading model…"},
            {tag: "warm model connected shortcut", phase: "idle", expected: "Ready"},
            {tag: "missing heartbeat", phase: "idle", disconnected: true, expected: "Connecting…"},
            {tag: "unread shortcut", phase: "idle", unread: true, expected: "Checking shortcut…"},
            {tag: "missing shortcut", phase: "idle", noShortcut: true, expected: "Set a shortcut"},
            {tag: "shortcut read failed", phase: "idle", keyError: true, expected: "Check shortcut"},
            {tag: "recording", phase: "recording", expected: "Recording"},
            {tag: "no window", phase: "recording", waiting: true, expected: "Recording · waiting for a window"},
            {tag: "finishing live output", phase: "finishing", expected: "Finishing…"},
            {tag: "after recording", phase: "transcribing", expected: "Transcribing…"},
            {tag: "offline", phase: "offline", expected: "Service unavailable"},
            {tag: "stopped", phase: "stopped", expected: "Service stopped"},
            {tag: "unrecognized state", phase: "bad", expected: "Status unavailable"}
        ];
    }
    function test_states(data) {
        compare(Status.label(data.phase, {frontend_available: !data.disconnected, waiting_for_focus: !!data.waiting},
                             data.models || 0, !data.unread, data.noShortcut ? "" : "F9", !!data.keyError), data.expected);
    }
    function test_overlay_labels() {
        compare(Status.overlayLabel("recording", true), "Preview");
        compare(Status.overlayLabel("recording", false), "Recording");
        compare(Status.overlayLabel("finishing", false), "Finishing…");
        compare(Status.overlayLabel("transcribing", false), "Transcribing…");
        compare(Status.overlayLabel("loading", false), "Loading model…");
    }
}
