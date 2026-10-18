.pragma library

function modifier(key, qt) {
    if (key === qt.Key_Control) return "CTRL"
    if (key === qt.Key_Alt) return "ALT"
    if (key === qt.Key_Shift) return "SHIFT"
    if (key === qt.Key_Meta || key === qt.Key_Super_L || key === qt.Key_Super_R) return "SUPER"
    return ""
}

function modifiers(mask, qt) {
    const result = []
    if (mask & qt.MetaModifier) result.push("SUPER")
    if (mask & qt.ControlModifier) result.push("CTRL")
    if (mask & qt.AltModifier) result.push("ALT")
    if (mask & qt.ShiftModifier) result.push("SHIFT")
    return result
}

function keyName(code, qt) {
    if ((code >= qt.Key_A && code <= qt.Key_Z) || (code >= qt.Key_0 && code <= qt.Key_9)) return String.fromCharCode(code)
    if (code >= qt.Key_F1 && code <= qt.Key_F35) return "F" + (code - qt.Key_F1 + 1)
    const names = {}
    names[qt.Key_Space] = "space"
    names[qt.Key_Return] = "Return"
    names[qt.Key_Enter] = "Return"
    names[qt.Key_Tab] = "Tab"
    names[qt.Key_Escape] = "Escape"
    names[qt.Key_Home] = "Home"
    names[qt.Key_End] = "End"
    names[qt.Key_PageUp] = "Prior"
    names[qt.Key_PageDown] = "Next"
    names[qt.Key_Insert] = "Insert"
    names[qt.Key_Delete] = "Delete"
    names[qt.Key_Backspace] = "BackSpace"
    names[qt.Key_Left] = "Left"
    names[qt.Key_Right] = "Right"
    names[qt.Key_Up] = "Up"
    names[qt.Key_Down] = "Down"
    names[qt.Key_Minus] = "minus"
    names[qt.Key_Equal] = "equal"
    names[qt.Key_Comma] = "comma"
    names[qt.Key_Period] = "period"
    return names[code] || ""
}

function capture(key, mask, qt) {
    const name = keyName(key, qt)
    const mods = modifiers(mask, qt)
    const text = mods.concat(name ? [name] : []).join(" + ")
    if (!name) return {text: text, error: "This key is not supported."}
    if (!/^F\d+$/.test(name) && !mods.some(value => value !== "SHIFT"))
        return {text: text, error: "Use Ctrl, Alt or Super with this key."}
    return {text: text, error: ""}
}
