import QtQuick.Controls as QQC
// Native Qt focus/click handling; appearance belongs to the shell theme.
QQC.Button {
    property bool focusable: true
    property bool bordered: false
    property bool selected: false
    focusPolicy: focusable ? Qt.StrongFocus : Qt.NoFocus
}
