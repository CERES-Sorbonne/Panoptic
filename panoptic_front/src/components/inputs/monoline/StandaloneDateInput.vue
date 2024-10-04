
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import VueDatePicker from '@vuepic/vue-datepicker'
import { pad } from '@/utils/utils';
import Dropdown from '@/components/dropdowns/Dropdown.vue';


const props = defineProps<{
    modelValue?: string
    width?: number
    teleport?: boolean
}>()
const emits = defineEmits(['update:modelValue', 'blur'])

defineExpose({
    forceFocus
})

let _no_reset_flag = false
let _mark_delete = false

const dateElem = ref(null)
const internal = ref(undefined)
const dropdownElem = ref(null)


const buttonStyle = computed(() => ({
    width: props.width ? props.width+'px' : '100%'
}))


const datePreview = computed(() => {
    if (internal.value == undefined) {
        return undefined
    }
    const date = new Date(internal.value)
    const res = date.getUTCFullYear() + '/' + pad(date.getUTCMonth()+1) + '/' + pad(date.getUTCDate()) + ' ' + pad(date.getUTCHours()) + ':' + pad(date.getUTCMinutes())

    return res
})

function save() {
    _no_reset_flag = true
    dateElem.value.selectDate()
    dropdownElem.value.hide()
    emits('update:modelValue', internal.value)
}

function cancel() {
    dropdownElem.value.hide()
    // localValue.value = propRef.value.value
}

function clear() {
    _no_reset_flag = true
    _mark_delete = true
    // dateElem.value.clearValue()
    dropdownElem.value.hide()
    emits('update:modelValue', undefined)
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


function updateLocalValue() {
    if(String(props.modelValue) == String(internal.value)) return

    if(props.modelValue) {
        internal.value = props.modelValue
    } else {
        internal.value = undefined
    }
    
}

function updateInternal(value: Date) {
    if(!value || _mark_delete) {
        _mark_delete = false
        internal.value = undefined
        return
    }
    internal.value = new Date(value.getTime() - value.getTimezoneOffset()*60*1000).toISOString()
}

function forceFocus() {
    console.log('force focus')
    dropdownElem.value.show()
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
    <Dropdown ref="dropdownElem" @hide="onHide" :teleport="props.teleport" >
        <template #button>
            <div class="drop-btn text-nowrap overflow-hidden" :style="buttonStyle" >
                <span v-if="internal">{{ datePreview }}</span>
                <span v-else class="text-secondary">None...</span>
            </div>


        </template>
        <template #popup>
            <VueDatePicker :model-value="props.modelValue"
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