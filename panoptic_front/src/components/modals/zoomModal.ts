import { Image } from "@/data/models";
import { reactive } from "vue";

export const zoomModal = reactive({
    open: false,
    image: undefined as Image,
    show: (img: Image) => { 
        zoomModal.image = img
        zoomModal.open = true
    },
    hide: () => {
        zoomModal.open = false
    }
})