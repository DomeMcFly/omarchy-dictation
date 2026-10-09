.pragma library

// Pure presentation of backend state; never infer model readiness from a folder.
function label(phase, status, modelCount, shortcutsLoaded, shortcut, shortcutError) {
    if (phase === "no-model") return modelCount > 0 ? "Choose a model" : "No model installed";
    if (phase === "model-error") return "Model unavailable";
    if (phase === "idle") {
        if (status.frontend_available !== true) return "Connecting…";
        if (shortcutError) return "Check shortcut";
        if (!shortcutsLoaded) return "Checking shortcut…";
        if (!shortcut) return "Set a shortcut";
        return "Ready";
    }
    if (phase === "recording" && status.waiting_for_focus) return "Recording · waiting for a window";
    return ({recording: "Recording", finishing: "Finishing…", transcribing: "Transcribing…",
             loading: "Loading model…", stopped: "Service stopped", offline: "Service unavailable"})[phase] || "Status unavailable";
}

function overlayLabel(phase, preview) {
    if (preview) return "Preview";
    return ({recording: "Recording", finishing: "Finishing…", transcribing: "Transcribing…",
             loading: "Loading model…"})[phase] || "";
}
