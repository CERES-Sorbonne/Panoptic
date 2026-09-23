import { useEventSignal } from "@/utils/utils";
import { onMounted, onUnmounted, reactive } from "vue";
import { useDataStore } from "../stores/dataStore";

export const keyState = reactive({
    ctrl: false,
    cmd: false,
    alt: false,
    shift: false,
    left: false,
    right: false,
    mouseX: 0,
    mouseY: 0,
    ctrlF: useEventSignal()
})

const isMac = navigator.userAgent.indexOf('Mac OS X') !== -1

// Don't steal Ctrl/Cmd+Z from a text field: there the browser's own undo is what the user means.
function isEditing(ev: KeyboardEvent) {
    const el = (ev.target ?? document.activeElement) as HTMLElement
    if (!el) return false
    const tag = el.tagName
    return tag == 'INPUT' || tag == 'TEXTAREA' || el.isContentEditable
}

function onKeyDown(ev: KeyboardEvent) {
    if (ev.key == 'Meta') keyState.cmd = true;
    if (ev.key == 'Control') keyState.ctrl = true;
    if (ev.key == 'Alt') {
        if (isMac) {
            keyState.ctrl = true
        }
        keyState.alt = true;
    }
    if (ev.key == 'Shift') keyState.shift = true;
    if (ev.key == 'ArrowLeft') keyState.left = true;
    if (ev.key == 'ArrowRight') { keyState.right = true; }

    // Undo / redo: Cmd+Z on mac, Ctrl+Z elsewhere (+Shift to redo). Read the modifiers off the
    // event rather than keyState: on mac Cmd never sets keyState.ctrl, and ev.key case depends on
    // Shift, so `ev.key == 'Z'` alone is not a reliable redo test.
    if (ev.key?.toLowerCase() == 'z' && (ev.metaKey || ev.ctrlKey) && !isEditing(ev)) {
        ev.preventDefault()
        const data = useDataStore()
        if (ev.shiftKey) data.redo()
        else data.undo()
    }

    if (ev.key == 'f' && (keyState.ctrl || keyState.cmd)) {
        ev.preventDefault()
        keyState.ctrlF.emit()
    }
}

function onKeyUp(ev: KeyboardEvent) {
    if (ev.key == 'Meta') keyState.cmd = false;
    if (ev.key == 'Control') keyState.ctrl = false;
    if (ev.key == 'Alt') {
        if (isMac) {
            keyState.ctrl = false
        }
        keyState.alt = false;
    }
    if (ev.key == 'Shift') keyState.shift = false;
    if (ev.key == 'ArrowLeft') keyState.left = false;
    if (ev.key == 'ArrowRight') keyState.right = false;
}

function onMouseMove(ev: MouseEvent) {
    keyState.ctrl = ev.ctrlKey
    keyState.alt = ev.altKey
    keyState.shift = ev.shiftKey
    keyState.cmd = ev.metaKey
    if (isMac) {
        keyState.ctrl = keyState.ctrl || keyState.alt
    }
    keyState.mouseX = ev.clientX
    keyState.mouseY = ev.clientY
}

/**
 * Keep keyState in sync with the keyboard and mouse, and fire its shortcuts, for as long
 * as the calling component is mounted. Call it from setup(); App.vue is the only caller.
 */
export function useKeyState() {
    onMounted(() => {
        window.addEventListener('keydown', onKeyDown)
        window.addEventListener('keyup', onKeyUp)
        window.addEventListener('mousemove', onMouseMove)
    })

    onUnmounted(() => {
        window.removeEventListener('keydown', onKeyDown)
        window.removeEventListener('keyup', onKeyUp)
        window.removeEventListener('mousemove', onMouseMove)
    })

    return keyState
}
