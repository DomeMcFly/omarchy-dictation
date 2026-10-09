pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import QtQuick.Dialogs as Dialogs
import QtQuick.Window as Windows
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons
import qs.Ui as Ui

Item {
    id: root
    required property var api
    property bool addingModel: false
    readonly property bool opened: window.open
    readonly property var geometry: ({x: window.cardOrigin.x, y: window.cardOrigin.y, width: window.contentWidth, height: window.contentHeight, scrollHeight: settingsScroll.height, fieldsHeight: settingsFields.implicitHeight, scrollable: settingsScroll.interactive, screen: window.screen ? window.screen.name : ""})
    function show() { window.open = true; }
    function hide() { modelDropdown.close(); styleDropdown.close(); positionDropdown.close(); screenDropdown.close(); window.open = false; }
    Windows.Window {
        id: dialogHost
        visible: false
        width: 1; height: 1
    }
    Dialogs.FolderDialog {
        id: modelFolder
        parentWindow: dialogHost
        title: "Choose a Parakeet TDT ONNX model folder"
        onAccepted: { root.api.selectModel(selectedFolder.toString()); root.api.show(); }
        onRejected: root.api.show()
    }
    component Caption: Text {
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        textFormat: Text.PlainText
    }
    component SectionHeading: Caption {
        font.pixelSize: Style.font.caption
        font.bold: true
        opacity: 0.65
        Layout.fillWidth: true
    }
    component CompactToggle: Ui.Button {
        property string label: ""
        property bool checked: false
        focusable: true
        implicitHeight: Style.space(30)
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Style.spacing.xs
            anchors.rightMargin: Style.spacing.xs
            Caption { text: parent.parent.label; Layout.fillWidth: true }
            Ui.ToggleSwitch { checked: parent.parent.checked; interactive: false }
        }
    }
    Ui.KeyboardPanel {
        id: window
        anchorItem: root.api.popupAnchor
        bar: root.api.popupBar
        owner: root.api.popupOwner || root.api
        focusTarget: content
        contentWidth: fittedContentWidth(Style.space(520))
        contentHeight: cappedContentHeight(contentHeader.implicitHeight + settingsFields.implicitHeight + content.spacing + window.padding * 2 + Border.top(window.borderSpec) + Border.bottom(window.borderSpec) + (recoveryBox.visible ? recoveryBox.implicitHeight + content.spacing : 0) + 2)
            ColumnLayout {
                id: content
                anchors.fill: parent
                spacing: Style.spacing.md
                focus: true
                Keys.onEscapePressed: root.api.hide()
                Ui.PanelHero {
                    id: contentHeader
                    Layout.fillWidth: true
                    title: "Dictation"
                    meta: root.api.statusLabel
                    iconComponent: Component {
                        Caption { text: "\uf130"; font.pixelSize: Style.font.display }
                    }
                    trailingControl: Component {
                        Ui.Button {
                            text: root.api.preview ? "Stop preview" : "Preview"
                            focusable: true
                            onClicked: root.api.preview = !root.api.preview
                        }
                    }
                }
                Flickable {
                    id: settingsScroll
                    Layout.fillWidth: true; Layout.fillHeight: true
                    contentWidth: width
                    contentHeight: settingsFields.implicitHeight
                    interactive: contentHeight > height + 1
                    boundsBehavior: Flickable.StopAtBounds
                    flickableDirection: Flickable.VerticalFlick
                    clip: true
                    onInteractiveChanged: if (!interactive) contentY = 0
                    QQC.ScrollBar.vertical: QQC.ScrollBar {
                        policy: settingsScroll.interactive ? QQC.ScrollBar.AsNeeded : QQC.ScrollBar.AlwaysOff
                    }
                    ColumnLayout {
                        id: settingsFields
                        width: settingsScroll.width
                        spacing: Style.spacing.md
                        SectionHeading { text: "DICTATION" }
                        SettingsDropdown {
                            id: modelDropdown
                            Layout.fillWidth: true
                            label: "Model"
                            enabled: !root.api.modelBusy
                            value: root.api.selectedModel
                            options: (root.api.selectedModel ? [] : [{value: "", label: root.api.modelCatalog.models.length ? "Choose a model" : "No model installed"}]).concat(root.api.modelCatalog.models).concat([{value: "__add__", label: "Add model…"}])
                            onChanged: value => {
                                if (value === "__add__") root.addingModel = !root.addingModel;
                                else if (value) { root.addingModel = false; root.api.selectModel(value); }
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: root.addingModel || root.api.modelCatalog.models.length === 0
                            Caption {
                                text: "Parakeet v3 · 2.55 GB · Hugging Face · CC BY 4.0"
                                font.pixelSize: Style.font.caption; wrapMode: Text.WordWrap; Layout.fillWidth: true
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Ui.Button {
                                    text: "Download recommended"; bordered: true; focusable: true
                                    enabled: !root.api.modelBusy
                                    onClicked: root.api.downloadModel()
                                }
                                Ui.Button {
                                    text: "Use model folder…"; focusable: true
                                    enabled: !root.api.modelBusy
                                    onClicked: { root.api.hide(); Qt.callLater(() => modelFolder.open()); }
                                }
                            }
                        }
                        Caption {
                            Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: Style.font.caption
                            text: root.api.downloadProgress >= 0 ? "Downloading · " + root.api.downloadProgress + "%" : root.api.status.model_error || root.api.modelMessage
                            visible: text.length > 0
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Caption { text: "Transcription" }
                            Ui.Button {
                                text: "Live"; bordered: true; focusable: true
                                Layout.fillWidth: true; Layout.preferredWidth: 1
                                selected: (root.api.prefs.transcription || "live") === "live"
                                onClicked: root.api.change("transcription", "live")
                            }
                            Ui.Button {
                                text: "After recording"; bordered: true; focusable: true
                                Layout.fillWidth: true; Layout.preferredWidth: 1
                                selected: root.api.prefs.transcription === "after"
                                onClicked: root.api.change("transcription", "after")
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Caption { text: "Shortcut" }
                            Ui.TextField {
                                id: primaryShortcut
                                Layout.fillWidth: true
                                text: root.api.shortcuts.primary
                                placeholderText: "F9"
                                enabled: !root.api.shortcutsBusy
                            }
                            Ui.Button {
                                text: root.api.shortcutsBusy ? "Applying…" : "Apply"
                                focusable: true
                                enabled: !root.api.shortcutsBusy && primaryShortcut.text.trim().length > 0 && primaryShortcut.text !== root.api.shortcuts.primary
                                onClicked: root.api.saveShortcuts(primaryShortcut.text)
                            }
                        }
                        Caption {
                            text: root.api.shortcutMessage
                            visible: text.length > 0
                            wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: Style.font.caption; color: Color.accent
                        }
                        Ui.PanelSeparator { Layout.fillWidth: true }

                        SectionHeading { text: "OVERLAY" }
                        CompactToggle {
                            Layout.fillWidth: true; label: "Show overlay"
                            checked: root.api.prefs.enabled !== false
                            onClicked: root.api.change("enabled", !checked)
                        }
                        SettingsDropdown {
                            id: styleDropdown
                            enabled: root.api.prefs.enabled !== false
                            opacity: enabled ? 1 : 0.4
                            Layout.fillWidth: true; label: "Style"; value: root.api.prefs.style
                            options: [{value: "wave", label: "Waveform"}, {value: "compact", label: "Compact"}, {value: "circle", label: "Pulsing circle"}]
                            onChanged: value => root.api.change("style", value)
                        }
                        SettingsDropdown {
                            id: positionDropdown
                            enabled: root.api.prefs.enabled !== false
                            opacity: enabled ? 1 : 0.4
                            Layout.fillWidth: true; label: "Position"; value: root.api.prefs.position
                            options: [
                                {value: "top-left", label: "Top left"}, {value: "top-center", label: "Top center"}, {value: "top-right", label: "Top right"},
                                {value: "center-left", label: "Center left"}, {value: "center-center", label: "Screen center"}, {value: "center-right", label: "Center right"},
                                {value: "bottom-left", label: "Bottom left"}, {value: "bottom-center", label: "Bottom center"}, {value: "bottom-right", label: "Bottom right"}]
                            onChanged: value => root.api.change("position", value)
                        }
                        SettingsDropdown {
                            id: screenDropdown
                            enabled: root.api.prefs.enabled !== false
                            opacity: enabled ? 1 : 0.4
                            Layout.fillWidth: true; label: "Screen"; value: root.api.prefs.monitor
                            options: [{value: "", label: "Follow active screen"}].concat(Quickshell.screens.map(s => ({value: s.name, label: s.name})))
                            onChanged: value => root.api.change("monitor", value)
                        }
                        Repeater {
                            model: [{key: "margin", label: "Margin · px", lo: 0, hi: 300}, {key: "size", label: "Size · %", lo: 60, hi: 180}, {key: "opacity", label: "Opacity · %", lo: 15, hi: 100}]
                            RowLayout {
                                required property var modelData
                                enabled: root.api.prefs.enabled !== false
                                opacity: enabled ? 1 : 0.4
                                Layout.fillWidth: true
                                Caption { text: modelData.label; font.pixelSize: Style.font.caption; Layout.preferredWidth: Style.space(88) }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Ui.PanelSlider {
                                        Layout.fillWidth: true
                                        minimum: modelData.lo; maximum: modelData.hi; integer: true; step: 1
                                        value: root.api.prefs[modelData.key]
                                        trackColor: Style.normalFillFor(Color.foreground, Color.accent)
                                        fillColor: Color.accent; knobColor: Color.foreground
                                        onMoved: value => root.api.change(modelData.key, Math.round(value))
                                    }
                                    Ui.NumberField {
                                        from: modelData.lo; to: modelData.hi
                                        value: root.api.prefs[modelData.key]
                                        fieldWidth: Style.space(76)
                                        onModified: value => root.api.change(modelData.key, value)
                                    }
                                }
                            }
                        }
                        Ui.PanelSeparator { Layout.fillWidth: true }
                        SectionHeading { text: "INDICATORS" }
                        CompactToggle {
                            Layout.fillWidth: true; label: "Highlight microphone"
                            enabled: root.api.prefs.enabled !== false
                            opacity: enabled ? 1 : 0.4
                            checked: root.api.prefs.highlightRecording !== false || root.api.prefs.enabled === false
                            onClicked: root.api.change("highlightRecording", !checked)
                        }
                        CompactToggle {
                            Layout.fillWidth: true; label: "Show overlay status"
                            enabled: root.api.prefs.enabled !== false
                            opacity: enabled ? 1 : 0.4
                            checked: root.api.prefs.label; onClicked: root.api.change("label", !checked)
                        }
                        CompactToggle {
                            Layout.fillWidth: true; label: "Animate overlay"
                            enabled: root.api.prefs.enabled !== false
                            opacity: enabled ? 1 : 0.4
                            checked: root.api.prefs.animate !== false; onClicked: root.api.change("animate", !checked)
                        }
                        Ui.Button { text: "Reset appearance"; focusable: true; onClicked: root.api.resetAppearance() }


                    }
                }
                ColumnLayout {
                    id: recoveryBox
                    Layout.fillWidth: true
                    visible: root.api.serviceUnavailable || root.api.messageError || root.api.recoveryError.length > 0
                    Caption {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                        color: Color.accent; font.pixelSize: Style.font.caption
                        text: root.api.messageError ? root.api.message : root.api.recoveryError || "Start the dictation service to continue."
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: Style.spacing.xs
                        Ui.Button {
                            text: "Start service"; focusable: true
                            visible: root.api.serviceUnavailable
                            onClicked: root.api.action("start-service")
                        }
                        Ui.Button {
                            text: "Copy latest"; focusable: true
                            visible: root.api.recoveryError.length > 0
                            onClicked: root.api.action("copy-last")
                        }
                        Ui.Button {
                            text: "Open dictations"; focusable: true
                            visible: root.api.recoveryError.length > 0
                            onClicked: root.api.action("open-history")
                        }
                        Ui.Button {
                            text: "Dismiss"; focusable: true
                            visible: root.api.messageError || root.api.recoveryError.length > 0
                            onClicked: {
                                root.api.messageError = false;
                                if (root.api.recoveryError.length > 0) root.api.action("dismiss-recovery");
                            }
                        }
                    }
                }
            }
    }
}
