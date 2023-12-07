/**
 * Main Store for Panoptic
 * Keeps all the raw data loaded from the Backend as a global truth
 * Main interface to modify data
 */

import { defineStore } from "pinia";
import { reactive, ref } from "vue";
import { Image, Property, TabIndex } from "./models";

export const useStore = defineStore('store', () => {
    const imageIndex = reactive({}) as { [imgId: number]: Image }
    const propertyIndex = reactive({} as { [propId: number]: Property })
    const tabIndex = reactive({}) as TabIndex



    return { imageIndex, propertyIndex, tabIndex }

})