import { Instance } from "@/data/models";
import { reactive } from "vue";

export const zoomModal = reactive({
    open: false,
    image: undefined as Instance,
    show: (img: Instance) => { 
        zoomModal.image = img
        zoomModal.open = true
    },
    hide: () => {
        zoomModal.open = false
    }
})