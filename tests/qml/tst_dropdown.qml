import QtQuick
import QtTest
import "../../omarchy-plugin" as Plugin

Item {
    id: scene
    width: 640; height: 600
    Plugin.SettingsDropdown {
        id: first
        x: 20; y: 20; width: 300
        label: "Style"; value: scene.selectedValue
        options: [{value: "wave", label: "Waveform"}, {value: "compact", label: "Compact"}, {value: "circle", label: "Circle"}]
        onChanged: value => scene.selectedValue = value
    }
    property string selectedValue: "wave"
    Plugin.SettingsDropdown {
        id: second
        x: 20; y: 250; width: 300
        label: "Position"; value: "bottom"
        options: [{value: "bottom", label: "Bottom"}, {value: "top", label: "Top"}]
    }
    TestCase {
        name: "DictationDropdown"
        when: windowShown
        function cleanup() { first.close(); second.close(); scene.selectedValue = "wave" }
        function trigger(control) { return findChild(control, "dropdownTrigger") }
        function clickTrigger(control) { mouseClick(trigger(control), 40, 16) }
        function test_second_click_closes_and_third_opens() {
            clickTrigger(first); tryCompare(first, "popupOpen", true)
            clickTrigger(first); tryCompare(first, "popupOpen", false)
            clickTrigger(first); tryCompare(first, "popupOpen", true)
        }
        function test_outside_click_closes() {
            clickTrigger(first); tryCompare(first, "popupOpen", true)
            mouseClick(scene, 580, 450); tryCompare(first, "popupOpen", false)
        }
        function test_escape_closes_only_dropdown() {
            clickTrigger(first); tryCompare(first, "popupOpen", true)
            keyClick(Qt.Key_Escape); tryCompare(first, "popupOpen", false)
            tryCompare(trigger(first), "activeFocus", true)
        }
        function test_switch_between_dropdowns() {
            clickTrigger(first); tryCompare(first, "popupOpen", true)
            clickTrigger(second); tryCompare(first, "popupOpen", false)
            tryCompare(second, "popupOpen", true)
        }
        function test_keyboard_selection_and_later_external_value() {
            clickTrigger(first); tryCompare(first, "popupOpen", true)
            keyClick(Qt.Key_Down); keyClick(Qt.Key_Return)
            tryCompare(first, "popupOpen", false)
            compare(scene.selectedValue, "compact")
            scene.selectedValue = "circle"; compare(first.currentLabel(), "Circle")
        }
        function test_mouse_selection_closes() {
            clickTrigger(first); tryCompare(first, "popupOpen", true)
            var list = findChild(first, "dropdownOptions")
            mouseClick(list, 40, 50)
            tryCompare(first, "popupOpen", false)
            compare(scene.selectedValue, "compact")
        }
    }
}
