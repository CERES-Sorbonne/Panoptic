import { useEventSignal } from "@/utils/utils";
import { reactive } from "vue";

export const keyState = reactive({
    ctrl: false,
    alt: false,
    shift: false,
    left: false,
    right: false,
    mouseX: 0,
    mouseY: 0,
    ctrlF: useEventSignal()
})

