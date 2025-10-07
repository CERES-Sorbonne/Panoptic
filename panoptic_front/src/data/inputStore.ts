/**
 * InputStore
 * Used to synchronize input states and allow navigation between inputs with tab press
 */

import { defineStore } from "pinia";
import { ref } from "vue";
import { keyState } from "./keyState";

export interface InputKey extends InputHash {
    key: string
    idx: number
}

export interface InputHash {
    groupId: number
    instanceId: number
}

export const useInputStore = defineStore('inputStore', () => {

    let inputIndex: { [key: string]: { [inputIdx: number]: InputHash } } = {}
    const openInput = ref<InputKey>()
    const requestInput = ref<InputKey>()

    function clear() {
        inputIndex = {}
        openInput.value = undefined
        requestInput.value = undefined
    }

    function addInput(key: string, idx: number, groupId: number, instanceId: number) {
        if (!inputIndex[key]) {
            inputIndex[key] = {}
        }
        inputIndex[key][idx] = { groupId, instanceId }
    }

    function removeInput(key: string, idx: number) {
        if (inputIndex[key]) {
            delete inputIndex[key][idx]
        }
    }

    function confirmOpen(key: string, idx: number, groupId: number, instanceId: number) {
        openInput.value = { key, idx, groupId, instanceId }
        requestInput.value = undefined
    }

    function requestInputNav() {
        if (keyState.shift) {
            requestPrevInput()
        }
        else {
            requestNextInput()
        }
    }

    function requestNextInput() {
        if (!openInput.value) {
            return
        }

        const inputs = Object.keys(inputIndex[openInput.value.key]).map(Number)
        inputs.sort((a, b) => a - b)
        const nextIdx = inputs.find(i => i > openInput.value.idx)
        const nextHash = inputIndex[openInput.value.key][nextIdx]
        requestInput.value = { key: openInput.value.key, idx: nextIdx, groupId: nextHash.groupId, instanceId: nextHash.instanceId }
    }

    function requestPrevInput() {
        if (!openInput.value) {
            return
        }

        const inputs = Object.keys(inputIndex[openInput.value.key]).map(Number)
        inputs.sort((a, b) => a - b)
        const nextIdx = inputs.findLast(i => i < openInput.value.idx)
        const nextHash = inputIndex[openInput.value.key][nextIdx]
        requestInput.value = { key: openInput.value.key, idx: nextIdx, groupId: nextHash.groupId, instanceId: nextHash.instanceId }
    }

    return {
        openInput, requestInput,
        clear,
        addInput, removeInput, confirmOpen, requestNextInput, requestPrevInput, requestInputNav
    }

})
