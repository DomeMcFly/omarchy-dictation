pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "Status.js" as Status

Scope {
    id: root
    property string omarchyPath: ""
    property var shell: null
    property var manifest: null
    property var prefs: ({position: "bottom-center", margin: 64, opacity: 85, size: 100, style: "wave", label: false, monitor: "", enabled: true, animate: true, highlightRecording: true})
    property var status: ({state: "offline", peak: 0})
    property double lastUpdate: 0
    property double now: Date.now()
    property bool preview: false
    property bool wantsOpen: false
    property string message: ""
    property bool messageError: false
    readonly property string recoveryError: status.recovery && status.recovery.error ? status.recovery.error : status.session_error || ""
    readonly property bool serviceUnavailable: phase === "offline" || phase === "stopped"
    property string frontendToken: Date.now().toString(36) + Math.random().toString(36).slice(2)
    function heartbeat() {
        if (widgets.length > 0 && !heartbeatProc.running) heartbeatProc.exec(["python3", helper, "frontend", frontendToken]);
    }
    Process { id: heartbeatProc; stdout: StdioCollector {} }
    Timer { interval: 1000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.heartbeat() }
    property bool loaded: false
    property var shortcuts: ({primary: "", alternative: ""})
    property bool shortcutsLoaded: false
    property bool shortcutError: false
    property string shortcutMessage: ""
    readonly property bool shortcutsBusy: keysProc.running
    readonly property string shortcutLabel: [shortcuts.primary, shortcuts.alternative].filter(k => k).join(" / ")
    function loadShortcuts() {
        if (!keysProc.running) { keysProc.result = ""; keysProc.exec(["python3", helper, "keys-read"]); }
    }
    function saveShortcuts(primary) {
        if (keysProc.running) return;
        shortcutMessage = "Checking and applying global shortcuts…";
        keysProc.result = "";
        keysProc.exec(["python3", helper, "keys-save", JSON.stringify({primary: primary, alternative: ""})]);
    }
    Component.onCompleted: { loadShortcuts(); refreshModels(); }
    Process {
        id: keysProc
        property string result: ""
        stdout: StdioCollector { onStreamFinished: keysProc.result = text }
        onExited: function(code) {
            try {
                let data = JSON.parse(result);
                if (code !== 0 || data.error) {
                    root.shortcutError = true;
                    root.shortcutMessage = data.error || "Could not change shortcuts.";
                }
                else {
                    root.shortcutError = false;
                    root.shortcuts = data;
                    root.shortcutsLoaded = true;
                    root.shortcutMessage = command[2] === "keys-save" ? "Applied globally · listed in Omarchy keybindings" : "";
                }
            } catch (error) { root.shortcutError = true; root.shortcutMessage = "Could not load global shortcuts."; }
        }
    }
    property var modelCatalog: ({models: [], selected: "", downloadBytes: 2549805955})
    property string modelMessage: ""
    property int downloadProgress: -1
    readonly property bool modelBusy: modelProc.running || phase === "loading"
    readonly property string selectedModel: status.model_path || modelCatalog.selected || ""
    function refreshModels() {
        if (!modelListProc.running) modelListProc.exec(["python3", helper, "model-list"]);
    }
    function selectModel(path) {
        if (modelBusy) return;
        modelMessage = "Loading model…";
        modelProc.exec(["python3", helper, "model-select", path]);
    }
    function downloadModel() {
        if (modelBusy) return;
        downloadProgress = 0;
        modelMessage = "Downloading model…";
        modelProc.exec(["python3", helper, "model-download"]);
    }
    Process {
        id: modelListProc
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    let data = JSON.parse(text);
                    if (data.error) root.modelMessage = data.error;
                    else {
                        root.modelCatalog = data;
                        if (data.configError) root.modelMessage = data.configError;
                    }
                } catch (error) { root.modelMessage = "Could not list models."; }
            }
        }
    }
    Process {
        id: modelProc
        property string downloaded: ""
        onStarted: downloaded = ""
        stdout: SplitParser {
            onRead: function(line) {
                try {
                    let data = JSON.parse(line);
                    if (data.progress !== undefined) root.downloadProgress = data.progress;
                    else if (data.error) root.modelMessage = data.error;
                    else if (data.downloaded) modelProc.downloaded = data.downloaded;
                } catch (error) { root.modelMessage = "Could not read model operation result."; }
            }
        }
        onExited: function(code) {
            root.downloadProgress = -1;
            if (code !== 0 && root.modelMessage.indexOf("…") >= 0) root.modelMessage = "Model operation failed. Please try again.";
            if (downloaded) {
                let path = downloaded;
                root.modelMessage = "Download complete";
                Qt.callLater(() => root.selectModel(path));
            }
            root.refreshModels();
        }
    }
    property string lastModelPath: ""
    onStatusChanged: {
        if (status.model_path && status.model_path !== lastModelPath) {
            lastModelPath = status.model_path;
            modelMessage = "";
            refreshModels();
        }
        if (status.state === "idle" && modelMessage === "Loading model…") modelMessage = "";
    }
    readonly property bool opened: settings.opened
    readonly property string helper: String(Qt.resolvedUrl("helper.py")).replace(/^file:\/\//, "")
    readonly property string phase: now - lastUpdate > 4000 ? "offline" : status.state
    readonly property string statusLabel: Status.label(phase, status, modelCatalog.models.length, shortcutsLoaded, shortcutLabel, shortcutError)

    property var widgets: []
    property Item popupAnchor: null
    property Item popupOwner: null
    property QtObject popupBar: null
    function registerWidget(widget) {
        if (widgets.indexOf(widget) < 0) widgets = widgets.concat([widget]);
    }
    function unregisterWidget(widget) {
        if (popupAnchor === widget.popupAnchor) { hide(); popupAnchor = null; popupOwner = null; popupBar = null; }
        widgets = widgets.filter(w => w && w !== widget);
    }
    function selectAnchor(widget) {
        let name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "";
        if (!widget) widget = widgets.find(w => w && w.QsWindow.window && w.QsWindow.window.screen.name === name) || widgets[0];
        if (!widget) { messageError = true; message = "Enable the Dictation widget in the bar."; return false; }
        popupAnchor = widget.popupAnchor;
        popupOwner = widget;
        popupBar = widget.bar;
        return true;
    }
    function show(widget) {
        if (!selectAnchor(widget)) return;
        loadShortcuts();
        refreshModels();
        wantsOpen = true;
        // Ask the real service before taking keyboard focus. File state alone
        // could be one frame behind an F9 press.
        if (!gate.running) gate.exec(["python3", helper, "status"]);
    }
    function hide() { wantsOpen = false; preview = false; flush(); settings.hide(); }
    function open() { show(); }
    function close() { hide(); }
    function toggle(widget) { if (opened || wantsOpen) hide(); else show(widget); }
    function change(key, value) {
        prefs = Object.assign({}, prefs, {[key]: value});
        saveTimer.restart();
    }
    function resetAppearance() {
        prefs = ({position: "bottom-center", margin: 64, opacity: 85, size: 100, style: "wave", label: false, monitor: "", enabled: true, animate: true, highlightRecording: true, transcription: prefs.transcription || "live"});
        saveTimer.restart();
    }
    function flush() {
        if (!loaded) return;
        if (saveProc.running) { saveTimer.restart(); return; }
        saveTimer.stop();
        saveProc.exec(["python3", helper, "save", JSON.stringify(prefs)]);
    }
    function action(name) {
        if (!actionProc.running) actionProc.exec(["python3", helper, name]);
    }
    Component.onDestruction: {
        Quickshell.execDetached(["python3", helper, "frontend-stop", frontendToken]);
        // A shell reload must not drop a pending change.
        if (loaded && (saveTimer.running || saveProc.running))
            Quickshell.execDetached(["python3", helper, "save", JSON.stringify(prefs)]);
    }
    Process {
        id: gate
        property bool activeDictation: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    let state = JSON.parse(text).state;
                    gate.activeDictation = state === "recording" || state === "finishing" || state === "transcribing";
                } catch (error) { gate.activeDictation = false; }
            }
        }
        onExited: {
            if (!root.wantsOpen) return;
            if (activeDictation) {
                root.message = "Finishing dictation first …";
                root.action("stop");
                finishGate.start();
            } else {
                root.wantsOpen = false;
                settings.show();
            }
        }
    }
    Timer {
        id: finishGate
        interval: 150; repeat: true
        onTriggered: {
            if (!root.wantsOpen) { stop(); return; }
            if (["idle", "offline", "stopped", "no-model", "model-error"].indexOf(root.phase) >= 0) {
                stop(); root.wantsOpen = false; settings.show();
                root.message = "Dictation finished. Settings are ready.";
            }
        }
    }
    Process {
        id: actionProc
        property string result: ""
        onStarted: result = ""
        stdout: StdioCollector { onStreamFinished: actionProc.result = text; }
        onExited: function(code) {
            try {
                let data = JSON.parse(result);
                root.messageError = code !== 0 || !!data.error;
                root.message = data.error ? data.error : command[2] === "copy-last" ? "Latest dictation copied." : "Action completed.";
            } catch (error) { root.messageError = code !== 0; root.message = code ? "Action failed." : "Action completed."; }
            root.heartbeat();
        }
    }
    Process {
        id: loadProc
        command: ["python3", root.helper, "read"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try { let data = JSON.parse(text); if (data.error) { root.messageError = true; root.message = data.error; } else root.prefs = data; }
                catch (error) { root.messageError = true; root.message = "Could not load settings."; }
                root.loaded = true;
            }
        }
    }
    Process {
        id: saveProc
        stdout: StdioCollector {}
        onExited: function(code) { if (code !== 0) { root.messageError = true; root.message = "Could not save settings."; } }
    }
    Timer { id: saveTimer; interval: 180; onTriggered: root.flush() }
    FileView {
        id: stateFile
        path: Quickshell.env("XDG_RUNTIME_DIR") + "/voice-dictation/state.json"
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoaded: { try { root.status = JSON.parse(text()); root.lastUpdate = Date.now(); } catch (error) {} }
        onLoadFailed: root.status = ({state: "offline", peak: 0})
    }
    Timer { interval: 500; running: true; repeat: true; onTriggered: root.now = Date.now() }
    Settings { id: settings; api: root }
    Hud { api: root }
    IpcHandler {
        target: "live-dictation"
        function show(): void { root.show(); }
        function showPreview(): void { root.show(); root.preview = true; }
        function hide(): void { root.hide(); }
        function toggle(): void { root.toggle(); }
        function status(): string { return JSON.stringify({state: root.phase, statusLabel: root.statusLabel, opened: root.opened, preferences: root.prefs, models: root.modelCatalog, modelBusy: root.modelBusy, modelMessage: root.modelMessage, shortcuts: root.shortcuts, panel: settings.geometry}); }
    }
}
