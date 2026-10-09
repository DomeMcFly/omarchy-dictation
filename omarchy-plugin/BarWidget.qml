import QtQuick
import qs.Commons
import qs.Ui as Ui

Ui.BarWidget {
    id: root
    moduleName: "dominic.live-dictation"
    readonly property var service: bar && bar.shell && typeof bar.shell.serviceFor === "function" ? bar.shell.serviceFor(moduleName) : null
    readonly property bool opened: service ? service.opened : false
    readonly property Item popupAnchor: button
    onServiceChanged: if (service) service.registerWidget(root)
    Component.onCompleted: if (service) service.registerWidget(root)
    Component.onDestruction: if (service) service.unregisterWidget(root)
    function show() { if (service) service.show(root) }
    function open() { show() }
    function hide() { if (service) service.hide() }
    function close() { hide() }
    function toggle() { if (service) service.toggle(root) }
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    Ui.BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "\uf130"
        active: root.service && root.service.phase === "recording" && (root.service.prefs.highlightRecording !== false || root.service.prefs.enabled === false)
        activeColor: root.service && root.service.prefs.enabled === false ? Color.urgent : Color.accent
        foreground: root.service && root.service.phase === "offline" ? Color.muted : Color.bar.text
        tooltipText: ""
        onPressed: function(buttonCode) { root.toggle() }
    }
}
