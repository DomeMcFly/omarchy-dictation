pragma Singleton
import QtQuick
// Theme-only fixture: the production dropdown and Qt popup event handling are real.
QtObject {
    property int normalBorderWidth: 1
    property int cornerRadius: 0
    property var font: ({family: "sans-serif", body: 14, caption: 12})
    property var spacing: ({controlHeight: 32, popupRowHeight: 32, dropdownWidth: 280,
        huge: 24, labelGap: 4, controlPaddingX: 8, md: 8, controlGap: 6, xxs: 2, hairline: 1})
    function controlFill() { return "#333333" }
    function hoverFillFor() { return "#555555" }
    function hoverStateColor() { return "#ffffff" }
}
