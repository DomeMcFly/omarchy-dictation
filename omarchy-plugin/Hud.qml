import QtQuick
import qs.Commons
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import "Status.js" as Status

Scope {
    id: root
    required property var api
    readonly property var status: api.status
    readonly property var settings: api.prefs
    property var levels: []
    property real smoothedEnergy: 0
    
    property double now: Date.now() / 1000
    readonly property string statusLabel: Status.overlayLabel(api.phase, preview)
    readonly property bool recording: api.phase === "recording"
    readonly property bool preview: api.preview && api.opened && !recording
    readonly property bool shown: preview || (settings.enabled !== false && ["recording", "finishing", "transcribing", "loading"].indexOf(api.phase) >= 0)
    function focusedScreenName() { return Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""; }
    function selectedScreen() {
        let name = settings.monitor || focusedScreenName();
        for (let s of Quickshell.screens) if (s.name === name) return s;
        // A disconnected fixed output falls back to the current workspace.
        for (let s of Quickshell.screens) if (s.name === focusedScreenName()) return s;
        return Quickshell.screens[0] || null;
    }
    onRecordingChanged: if (recording) { levels = []; smoothedEnergy = 0; }
    Timer {
        interval: 100; running: root.shown; repeat: true
        onTriggered: {
            root.now = Date.now() / 1000;
            let values = root.levels.slice(-27);
            let energy = root.settings.animate === false ? 0.35
                : root.preview ? 0.15 + 0.65 * Math.abs(Math.sin(root.now * 3.1) * Math.cos(root.now * 1.7))
                : Math.min(1, Math.sqrt(root.status.peak || 0) * 1.7);
            root.smoothedEnergy += (energy - root.smoothedEnergy) * (energy > root.smoothedEnergy ? 0.65 : 0.3);
            values.push(root.settings.animate === false ? 0.35 : root.smoothedEnergy);
            root.levels = values;
        }
    }
    PanelWindow {
        id: panel
        screen: root.selectedScreen()
        visible: root.shown
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "voice-dictation-osd"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        mask: Region { intersection: Intersection.Subtract; width: panel.width; height: panel.height }
        Item {
            id: pill
            readonly property real factor: (root.settings.size || 100) / 100
            readonly property bool circle: root.settings.style === "circle"
            readonly property bool compact: root.settings.style === "compact"
            readonly property bool animated: root.recording || root.preview
            readonly property color accent: animated ? Color.accent : Color.foreground
            readonly property real energy: root.levels.length ? root.levels[root.levels.length - 1] : 0
            readonly property real circleLabelHeight: circle && root.settings.label ? circleStatus.implicitHeight + 6 * factor : 0
            width: circle ? Math.max(46 * factor, root.settings.label ? circleStatus.implicitWidth + 16 * factor : 0)
                : ((compact ? 84 : 146) + (root.settings.label ? statusText.implicitWidth / factor + 10 : 0)) * factor
            height: (circle ? 46 : 40) * factor + circleLabelHeight
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: pill.circle ? 46 * pill.factor : parent.width
                height: (pill.circle ? 46 : 40) * pill.factor
                radius: pill.circle ? height / 2 : Style.cornerRadius
                color: Color.popups.background
                border.width: 1
                border.color: Color.popups.border
            }
            Text {
                id: circleStatus
                visible: pill.circle && root.settings.label
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                text: root.statusLabel
                color: Color.popups.text
                font.family: Style.font.family
                font.pixelSize: Style.font.caption * pill.factor
                style: Text.Outline; styleColor: Color.popups.background
            }
            opacity: (root.settings.opacity || 85) / 100
            x: root.settings.position.endsWith("left") ? Math.min(root.settings.margin, Math.max(0, panel.width - width))
                : root.settings.position.endsWith("right") ? Math.max(0, panel.width - width - root.settings.margin)
                : (panel.width - width) / 2
            y: root.settings.position.startsWith("top") ? Math.min(root.settings.margin, Math.max(0, panel.height - height))
                : root.settings.position.startsWith("bottom") ? Math.max(0, panel.height - height - root.settings.margin)
                : (panel.height - height) / 2
            Item {
                id: circleVisual
                visible: pill.circle
                anchors.horizontalCenter: parent.horizontalCenter
                y: (46 * pill.factor - height) / 2
                width: 38 * pill.factor
                height: width
                readonly property bool moving: root.shown && pill.circle && pill.animated && root.settings.animate !== false
                property real envelope: moving ? Math.pow(Math.max(0, Math.min(1, pill.energy)), 0.75) : 0
                property real breath: 0
                Behavior on envelope {
                    SmoothedAnimation { velocity: 1.6; maximumEasingTime: 300; reversingMode: SmoothedAnimation.Immediate }
                }
                SequentialAnimation on breath {
                    running: circleVisual.moving
                    loops: Animation.Infinite
                    NumberAnimation { to: 1; duration: 1400; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0; duration: 1400; easing.type: Easing.InOutSine }
                }
                onMovingChanged: if (!moving) breath = 0
                Rectangle {
                    anchors.centerIn: parent
                    width: 34 * pill.factor; height: width; radius: width / 2
                    scale: 0.78 + circleVisual.envelope * 0.40 + circleVisual.breath * 0.04
                    color: pill.accent
                    opacity: 0.07 + circleVisual.envelope * 0.12
                    antialiasing: true
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: 26 * pill.factor; height: width; radius: width / 2
                    scale: 0.88 + circleVisual.envelope * 0.62 + circleVisual.breath * 0.05
                    color: "transparent"
                    border.width: 1.5 * pill.factor; border.color: pill.accent
                    opacity: 0.8 + circleVisual.envelope * 0.2
                    antialiasing: true
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: 7 * pill.factor; height: width; radius: width / 2
                    color: pill.accent
                    antialiasing: true
                }
            }
            Row {
                visible: !pill.circle
                anchors.centerIn: parent
                height: 22 * pill.factor
                spacing: 10 * pill.factor
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 6 * pill.factor; height: width; radius: width / 2
                    color: pill.accent
                }
                Item {
                    width: (pill.compact ? 32 : 92) * pill.factor
                    height: 22 * pill.factor
                    Row {
                        anchors.centerIn: parent
                        height: parent.height
                        spacing: (pill.compact ? 4 : 1.3) * pill.factor
                        Repeater {
                            model: pill.compact ? 5 : 28
                            Item {
                                required property int index
                                width: (pill.compact ? 3 : 2) * pill.factor
                                height: 22 * pill.factor
                                Rectangle {
                                    anchors.centerIn: parent
                                    width: parent.width
                                    height: Math.max(3, pill.animated ? (root.levels[pill.compact ? parent.index * 5 : parent.index] || 0) * 22 : 3) * pill.factor
                                    radius: width / 2; color: pill.accent
                                    Behavior on height { enabled: root.settings.animate !== false; NumberAnimation { duration: 110; easing.type: Easing.InOutSine } }
                                }
                            }
                        }
                    }
                }
                Text {
                    id: statusText
                    visible: root.settings.label
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.statusLabel
                    color: Color.popups.text; font.family: Style.font.family; font.pixelSize: Style.font.caption * pill.factor
                }
            }
        }
    }
}
