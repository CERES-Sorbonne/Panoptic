import { defineStore } from "pinia";
import { ModalId } from "./models";
import { computed, reactive, shallowRef } from "vue";

export const useModalStore = defineStore('modalStore', () => {
    
    const idIndex: {[id: string]: number} = reactive({})
    const layerOpen = shallowRef<{[layer: number]: {id: ModalId, data: any}}>({})

    const openIndex = computed<{[id: string]: Boolean}>(() => {
        const res = {}
        const open = layerOpen.value
        for(let modal of Object.values(open)) {
            res[modal.id] = true
        }
        console.log('update computed')
        return res
    })

    function registerModal(id: ModalId, layer: number = 0) {
        idIndex[id] = layer
    }

    function openModal(id: ModalId, data?: any) {
        data = data ?? {}
        const layer = idIndex[id]
        if(layer === undefined) return
        const open = {...layerOpen.value}
        open[layer] = {id, data}
        layerOpen.value = open
        console.log('set data', data)
    }

    function closeModal(id: ModalId) {
        const layer = idIndex[id]
        if(layer === undefined) return
        const open = {...layerOpen.value}
        delete open[layer]
        layerOpen.value = open
    }

    function getData(id: ModalId) {
        const layer = idIndex[id]
        const data = layerOpen.value[layer]?.data
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