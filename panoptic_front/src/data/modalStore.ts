import { defineStore } from "pinia";
import { ModalId } from "./models";
import { computed, reactive } from "vue";

export const useModalStore = defineStore('modalStore', () => {
    
    const idIndex: {[id: string]: number} = reactive({})
    const layerOpen: {[layer: number]: {id: ModalId, data: any}} = reactive({})

    const openIndex = computed<{[id: string]: Boolean}>(() => {
        const res = {}
        for(let modal of Object.values(layerOpen)) {
            res[modal.id] = true
        }
        return res
    })

    function registerModal(id: ModalId, layer: number = 0) {
        idIndex[id] = layer
    }

    function openModal(id: ModalId, data?: any) {
        data = data ?? {}
        const layer = idIndex[id]
        if(layer === undefined) return
        layerOpen[layer] = {id, data}
    }

    function closeModal(id: ModalId) {
        const layer = idIndex[id]
        if(layer === undefined) return
        delete layerOpen[layer]
    }

    function getData(id: ModalId) {
        const layer = idIndex[id]
        const data = layerOpen[layer]?.data
        if(layer === undefined) return
        if(!openIndex.value[id]) return
        return data
    }

    function isOpen(id: ModalId) {
        return openIndex.value[id]
    }


    return {
        idIndex, layerOpen, openIndex,
        registerModal, openModal, closeModal, isOpen,
        getData
    }
})