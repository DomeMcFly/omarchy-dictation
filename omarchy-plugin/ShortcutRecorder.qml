import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui as Ui
import "ShortcutCapture.js" as Capture

FocusScope {
    id: root
    property string value: ""
    property bool busy: false
    property bool captureReady: true
    property string externalError: ""
    property bool replacementAvailable: false
    property string draft: ""
    property string modifierPreview: ""
    property string inputError: ""
    property int heldKey: 0
    property bool draftValid: false
    readonly property string errorText: inputError || externalError
    readonly property string displayText: modifierPreview || draft || value || "Not set"
    readonly property bool pending: modifierPreview.length > 0 || draft.length > 0
    readonly property bool canApply: !busy && captureReady && draftValid && !modifierPreview && !errorText && draft !== value
    readonly property bool canReplace: !busy && captureReady && draftValid && !modifierPreview && !inputError && externalError.length > 0 && replacementAvailable && draft !== value
    signal saveRequested(string shortcut)
    signal replaceRequested(string shortcut)
    signal cancelled()
    signal editingStarted()

    implicitHeight: controls.implicitHeight
    implicitWidth: controls.implicitWidth
    onValueChanged: reset()
    onActiveFocusChanged: if (!activeFocus && !busy) reset()

    function reset() {
        draft = ""; modifierPreview = ""; inputError = ""; heldKey = 0; draftValid = false;
    }
    function begin() {
        reset(); editingStarted(); field.forceActiveFocus();
    }
    function keyPressed(event) {
        event.accepted = true;
        if (busy || !captureReady || event.isAutoRepeat) return;
        const mods = Capture.modifiers(event.modifiers, Qt);
        if ((event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) && mods.every(value => value === "SHIFT")) {
            event.accepted = false;
            return;
        }
        if ((event.key === Qt.Key_Backspace || event.key === Qt.Key_Escape) && mods.length === 0) {
            reset(); editingStarted();
            if (event.key === Qt.Key_Escape) cancelled();
            return;
        }
        const modifier = Capture.modifier(event.key, Qt);
        if (modifier) {
            if (mods.indexOf(modifier) < 0) mods.push(modifier);
            modifierPreview = mods.join(" + ") + " + …";
            draft = ""; draftValid = false; inputError = ""; editingStarted();
            return;
        }
        if (heldKey && heldKey !== event.key) {
            inputError = "Use one main key with Ctrl, Alt, Shift or Super.";
            draftValid = false;
            return;
        }
        heldKey = event.key;
        const result = Capture.capture(event.key, event.modifiers, Qt);
        modifierPreview = ""; draft = result.text; inputError = result.error;
        draftValid = !result.error;
        editingStarted();
    }
    function keyReleased(event) {
        event.accepted = true;
        if (event.key === heldKey) heldKey = 0;
        if (!modifierPreview) return;
        const released = Capture.modifier(event.key, Qt);
        const remaining = Capture.modifiers(event.modifiers, Qt).filter(value => value !== released);
        modifierPreview = remaining.length ? remaining.join(" + ") + " + …" : "";
    }

    ColumnLayout {
        id: controls
        anchors.left: parent.left; anchors.right: parent.right
        spacing: Style.spacing.xxs
        RowLayout {
            Layout.fillWidth: true
            uniformCellSizes: true
            Ui.BorderSurface {
                id: field
                objectName: "shortcutField"
                Layout.fillWidth: true
                Layout.preferredWidth: Style.space(140)
                Layout.minimumWidth: Style.space(140)
                implicitHeight: Style.spacing.controlHeight
                activeFocusOnTab: true
                borderSpec: Border.controlSpec(activeFocus ? "focus" : (hover.hovered ? "hover-cursor" : "normal"), Color.foreground, root.errorText ? Color.urgent : Color.accent)
                color: Style.controlFill(activeFocus, hover.hovered, Color.foreground, Color.accent)
                radius: Style.cornerRadius
                HoverHandler { id: hover }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.begin() }
                Keys.priority: Keys.BeforeItem
                Keys.onPressed: event => root.keyPressed(event)
                Keys.onReleased: event => root.keyReleased(event)
                onActiveFocusChanged: if (activeFocus) root.editingStarted()
                Text {
                    anchors.centerIn: parent
                    width: parent.width - 16
                    horizontalAlignment: Text.AlignHCenter
                    text: root.displayText
                    textFormat: Text.PlainText
                    font.family: Style.font.family; font.pixelSize: Style.font.body
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Style.font.caption
                    color: root.errorText ? Color.urgent : Color.foreground
                    opacity: root.pending && !root.errorText ? 0.65 : 1
                }
            }
            Ui.Button {
                objectName: "shortcutApply"
                text: root.busy ? "Applying…" : root.canReplace ? "Replace Voxtype" : "Apply"
                Layout.fillWidth: true
                Layout.preferredWidth: Style.space(140)
                Layout.fillHeight: true
                bordered: true
                selected: root.canApply || root.canReplace
                opacity: enabled ? 1 : 0.4
                focusable: true
                enabled: root.canApply || root.canReplace
                onClicked: {
                    if (root.canReplace) root.replaceRequested(root.draft);
                    else root.saveRequested(root.draft);
                }
            }
        }
        Text {
            Layout.fillWidth: true
            visible: root.errorText.length > 0
            text: root.errorText
            textFormat: Text.PlainText
            color: Color.urgent
            font.family: Style.font.family; font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
        }
    }
}
