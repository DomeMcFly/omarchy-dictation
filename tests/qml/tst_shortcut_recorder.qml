import QtQuick
import QtQuick.Controls
import QtTest
import "../../omarchy-plugin" as Plugin

Item {
    id: scene
    width: 600; height: 300
    property string saved: "F9"
    Plugin.ShortcutRecorder {
        id: recorder
        x: 20; y: 20; width: 500
        value: scene.saved
        onSaveRequested: shortcut => scene.saved = shortcut
        onCancelled: outside.forceActiveFocus()
    }
    Button { id: outside; x: 20; y: 150; text: "Other setting"; focusPolicy: Qt.StrongFocus }
    SignalSpy { id: saves; target: recorder; signalName: "saveRequested" }
    SignalSpy { id: replacements; target: recorder; signalName: "replaceRequested" }
    TestCase {
        name: "DictationShortcutRecorder"
        when: windowShown
        function field() { return findChild(recorder, "shortcutField") }
        function apply() { return findChild(recorder, "shortcutApply") }
        function begin() { mouseClick(field(), 40, 16); tryCompare(field(), "activeFocus", true) }
        function cleanup() {
            outside.forceActiveFocus(); scene.saved = "F9"; recorder.captureReady = true;
            recorder.externalError = ""; recorder.replacementAvailable = false;
            recorder.reset(); saves.clear(); replacements.clear();
        }
        function test_modifier_preview_and_backspace_reset() {
            begin(); keyPress(Qt.Key_Control);
            compare(recorder.displayText, "CTRL + …"); verify(!recorder.canApply);
            keyRelease(Qt.Key_Control);
            keyClick(Qt.Key_H, Qt.ControlModifier);
            compare(recorder.displayText, "CTRL + H"); verify(recorder.pending); verify(recorder.canApply);
            keyClick(Qt.Key_Backspace);
            compare(recorder.displayText, "F9"); verify(!recorder.pending); compare(scene.saved, "F9");
        }
        function test_controls_share_width_without_clipping() {
            wait(0);
            verify(Math.abs(field().width - apply().width) <= 1);
            verify(apply().width >= apply().implicitWidth);
            verify(apply().mapToItem(recorder, apply().width, 0).x <= recorder.width + 1);
        }
        function test_apply_is_explicit_and_reset_uses_new_saved_value() {
            begin(); keyClick(Qt.Key_H, Qt.ControlModifier);
            compare(scene.saved, "F9"); compare(saves.count, 0);
            mouseClick(apply()); compare(saves.count, 1); compare(scene.saved, "CTRL + H");
            begin(); keyClick(Qt.Key_G, Qt.AltModifier); keyClick(Qt.Key_Backspace);
            compare(recorder.displayText, "CTRL + H");
        }
        function test_blur_discards_without_applying() {
            begin(); keyClick(Qt.Key_H, Qt.ControlModifier);
            mouseClick(outside); tryCompare(recorder, "activeFocus", false);
            compare(recorder.displayText, "F9"); compare(saves.count, 0);
        }
        function test_super_shift_and_function_keys() {
            begin(); keyClick(Qt.Key_H, Qt.MetaModifier | Qt.ShiftModifier);
            compare(recorder.displayText, "SUPER + SHIFT + H"); verify(recorder.canApply);
            keyClick(Qt.Key_F10); compare(recorder.displayText, "F10"); verify(recorder.canApply);
        }
        function test_plain_letter_and_two_main_keys_are_rejected() {
            begin(); keyClick(Qt.Key_H); verify(recorder.errorText.length > 0); verify(!recorder.canApply);
            keyPress(Qt.Key_H, Qt.ControlModifier); keyPress(Qt.Key_G, Qt.ControlModifier);
            verify(recorder.errorText.indexOf("one main key") >= 0); verify(!recorder.canApply);
            keyRelease(Qt.Key_G, Qt.ControlModifier); keyRelease(Qt.Key_H, Qt.ControlModifier);
        }
        function test_escape_restores_saved_and_leaves_recorder() {
            begin(); keyClick(Qt.Key_H, Qt.ControlModifier); keyClick(Qt.Key_Escape);
            compare(recorder.displayText, "F9"); tryCompare(recorder, "activeFocus", false);
        }
        function test_capture_waits_for_inhibitor_and_guard() {
            recorder.captureReady = false;
            begin(); keyClick(Qt.Key_H, Qt.ControlModifier);
            compare(recorder.displayText, "F9"); verify(!recorder.canApply);
        }
        function test_conflict_disables_apply_until_new_input() {
            begin(); keyClick(Qt.Key_H, Qt.ControlModifier);
            verify(recorder.canApply);
            recorder.externalError = "Already used: CTRL + H";
            verify(!recorder.canApply); verify(!apply().enabled);
            recorder.externalError = "";
            keyClick(Qt.Key_G, Qt.ControlModifier);
            verify(recorder.canApply);
        }
        function test_f9_from_fn_keyboard_is_a_regular_function_key() {
            scene.saved = "ALT + K";
            begin(); keyClick(Qt.Key_F9);
            compare(recorder.displayText, "F9"); verify(recorder.canApply);
        }
        function test_voxtype_replacement_requires_separate_explicit_click() {
            scene.saved = "ALT + K";
            begin(); keyClick(Qt.Key_F9);
            recorder.externalError = "Used by Omarchy Voxtype: F9";
            recorder.replacementAvailable = true;
            verify(!recorder.canApply); verify(recorder.canReplace);
            compare(apply().text, "Replace Voxtype"); compare(replacements.count, 0);
            mouseClick(apply()); compare(replacements.count, 1);
            compare(replacements.signalArguments[0][0], "F9"); compare(saves.count, 0);
            compare(scene.saved, "ALT + K");
        }
        function test_no_default_is_invented_when_unconfigured() {
            scene.saved = ""; compare(recorder.displayText, "Not set");
        }
    }
}
