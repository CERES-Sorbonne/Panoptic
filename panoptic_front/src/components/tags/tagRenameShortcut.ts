// Cmd/Ctrl-click on any tag badge opens the rename modal.
// One capture-phase listener on window serves every badge in the app, so tag lists and
// scrollers pay nothing per badge beyond the data-tag-id attribute TagBadge renders.
// The modified press is swallowed before any component sees it: a badge's own mousedown
// (drag, selection, opening a dropdown) never runs for a rename gesture.

import { ModalId } from '@/data/models'
import { useModalStore } from '@/data/stores/modalStore'

// The tag pressed with the modifier held, waiting for the click (or, for ctrl-click on macOS,
// the contextmenu event the browser fires in place of the click).
let armedTagId: number | undefined

function tagIdAt(e: MouseEvent): number | undefined {
    const target = e.target as Element | null
    const badge = target?.closest?.('[data-tag-id]')
    if (!badge) return
    const id = Number(badge.getAttribute('data-tag-id'))
    return Number.isFinite(id) ? id : undefined
}

function swallow(e: Event) {
    e.preventDefault()
    e.stopPropagation()
}

function onMouseDown(e: MouseEvent) {
    armedTagId = undefined
    if (e.button !== 0 || !(e.metaKey || e.ctrlKey)) return
    const id = tagIdAt(e)
    if (id === undefined) return
    armedTagId = id
    swallow(e)
}

function open(e: Event) {
    const id = armedTagId
    armedTagId = undefined
    swallow(e)
    useModalStore().openModal(ModalId.RENAME_TAG, { tagId: id })
}

function onClick(e: MouseEvent) {
    if (armedTagId === undefined) return
    if (tagIdAt(e) !== armedTagId) {
        armedTagId = undefined
        return
    }
    open(e)
}

function onContextMenu(e: MouseEvent) {
    if (armedTagId === undefined || !e.ctrlKey) return
    if (tagIdAt(e) !== armedTagId) return
    open(e)
}

export function installTagRenameShortcut() {
    window.addEventListener('mousedown', onMouseDown, true)
    window.addEventListener('click', onClick, true)
    window.addEventListener('contextmenu', onContextMenu, true)
}

export function uninstallTagRenameShortcut() {
    window.removeEventListener('mousedown', onMouseDown, true)
    window.removeEventListener('click', onClick, true)
    window.removeEventListener('contextmenu', onContextMenu, true)
    armedTagId = undefined
}
