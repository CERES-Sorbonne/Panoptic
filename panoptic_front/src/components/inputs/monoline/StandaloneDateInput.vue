
<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { DeprecationTypes, computed, nextTick, onMounted, ref, watch } from 'vue';
import VueDatePicker from '@vuepic/vue-datepicker'
import { useProjectStore } from '@/data/projectStore'
import { getImageProperty, pad } from '@/utils/utils';
import Dropdown from '@/components/dropdowns/Dropdown.vue';


const props = defineProps({
    modelValue: Date,
    width: Number
})
const emits = defineEmits(['update:modelValue', 'blur'])

let _no_reset_flag = false

const dateElem = ref(null)
const focusElem = ref(null)
const internal = ref(null as Date)
const dropdownElem = ref(null)


const buttonStyle = computed(() => ({
    width: props.width ? props.width+'px' : '100%'
}))


const datePreview = computed(() => {
    const date = internal.value
    if (date == undefined) {
        return undefined
    }
    
    const res = date.getUTCFullYear() + '/' + pad(date.getUTCMonth()+1) + '/' + pad(date.getUTCDate()) + ' ' + pad(date.getUTCHours()) + ':' + pad(date.getUTCMinutes())

    return res
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
    if(props.modelValue == internal.value) return

    if(props.modelValue) {
        internal.value = new Date(props.modelValue)
    } else {
        internal.value = undefined
    }
    
}

function updateInternal(value: Date) {
    internal.value = new Date(value.getTime() - value.getTimezoneOffset()*60*1000)
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
    <Dropdown ref="dropdownElem" @hide="onHide" :teleport="true" >
        <template #button>
            <div class="drop-btn text-nowrap overflow-hidden" :style="buttonStyle" >
                <span v-if="internal">{{ datePreview }}</span>
                <span v-else class="text-secondary">None...</span>
            </div>


        </template>
        <template #popup>
            <VueDatePicker :model-value="props.modelValue" @update:model-value="e => emits('update:modelValue', e)"
                input-class-name="custom-date-picker" :hide-input-icon="true" utc="preserve" format="yyyy/MM/dd HH:mm"
                @internal-model-change="e => updateInternal(e)"
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