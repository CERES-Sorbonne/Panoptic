
<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { DeprecationTypes, computed, nextTick, onMounted, ref, watch } from 'vue';
import VueDatePicker from '@vuepic/vue-datepicker'
import { useStore } from '@/data/store'
import { getImageProperty } from '@/utils/utils';
import Dropdown from '@/components/dropdowns/Dropdown.vue';


const props = defineProps({
    modelValue: Date,
    width: Number
})
const emits = defineEmits(['update:modelValue', 'blur'])

let _no_reset_flag = false

const dateElem = ref(null)
const focusElem = ref(null)
const internal = ref(null)
const dropdownElem = ref(null)


const buttonStyle = computed(() => ({
    width: props.width ? props.width+'px' : '100%'
}))


const datePreview = computed(() => {
    if (internal.value == undefined) {
        return undefined
    }
    const formattedDate = internal.value.toLocaleString("fr-FR", {
        day: "numeric",
        month: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit"
    })
    return formattedDate
})

function save() {
    _no_reset_flag = true
    dateElem.value.selectDate()
    dropdownElem.value.hide()
}

function cancel() {
    dropdownElem.value.hide()
    // localValue.value = propRef.value.value
}

function clear() {
    _no_reset_flag = true
    dateElem.value.clearValue()
    dropdownElem.value.hide()
    // globalStore.setPropertyValue(props.property.id, props.image, undefined)
}

function onHide() {
    emits('blur')
    if(!dateElem.value) return
    
    dateElem.value.closeMenu()
    if(_no_reset_flag) {
        _no_reset_flag = false
    } else {
        updateLocalValue()
    }
}

function onEsc() {
    console.log('la')
}

function updateLocalValue() {
    if(props.modelValue) {
        internal.value = new Date(props.modelValue)
    } else {
        internal.value = undefined
    }
    
}

watch(props, ()=> {
    if(String(props.modelValue) != String(internal.value)) {
        updateLocalValue()
    }
})

onMounted(() => {
    updateLocalValue()
})



</script>

<template>
    <Dropdown ref="dropdownElem" @hide="onHide">
        <template #button>
            <div class="drop-btn text-nowrap overflow-hidden" :style="buttonStyle" >
                <span v-if="internal">{{ datePreview }}</span>
                <span v-else class="text-secondary">None...</span>
            </div>


        </template>
        <template #popup>
            <VueDatePicker :model-value="props.modelValue" @update:model-value="e => emits('update:modelValue', e)"
                :teleport="true" input-class-name="custom-date-picker" :hide-input-icon="true"
                @internal-model-change="e => internal = e"
                calendar-cell-class-name="custom-date-picker" :inline="true" ref="dateElem">
                <template #action-buttons>
                    <span style="font-size: 13px;" class="text-nowrap">
                        <span class="base-btn me-1" @click="clear"><i class="bi bi-trash" /></span>
                        <span class="base-btn me-1 border" @click="cancel">cancel</span>
                        <span v-if="(props.modelValue != undefined) || internal" class="me-1 base-btn border"
                            @click="save">save</span>
                    </span>
                </template>
            </VueDatePicker>
        </template>
    </Dropdown>
</template>

<style scoped>
.drop-btn {
    cursor: pointer;
}
</style>