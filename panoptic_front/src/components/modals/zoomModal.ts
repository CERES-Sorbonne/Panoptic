import { Instance } from "@/data/models";
import { reactive } from "vue";

// `owner` is the id of the Zoomable that opened the modal. Only that one may close it:
// the same image can be shown by several Zoomables at once (a recycled, hidden scroller
// line, the grid behind the image modal...), and the others must not react.
let nextOwner = 0
// A fresh owner id for a component that opens the modal.
export function newZoomOwner(): number {
    return nextOwner++
}

export const zoomModal = reactive({
    open: false,
    image: undefined as Instance,
    owner: null as number | null,
    show: (img: Instance, owner: number) => {
        zoomModal.image = img
        zoomModal.owner = owner
        zoomModal.open = true
    },
    hide: (owner: number) => {
        if (zoomModal.owner !== owner) return
        zoomModal.open = false
        zoomModal.owner = null
    }
})
