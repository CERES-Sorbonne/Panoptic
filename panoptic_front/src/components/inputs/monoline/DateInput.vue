
<script setup lang="ts">
import { Image, Property } from '@/data/models';
import { computed, onMounted, ref, watch } from 'vue';
import VueDatePicker from '@vuepic/vue-datepicker'
import { globalStore } from '@/data/store';
import { getImageProperty } from '@/utils/utils';


const props = defineProps({
    image: Object as () => Image,
    property: Object as () => Property
})

const dateElem = ref(null)
const localValue = ref(null)

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))

function save() {
    dateElem.value.selectDate()
    globalStore.setPropertyValue(props.property.id, props.image, localValue.value)
}

function cancel() {
    dateElem.value.closeMenu()
}

function clear() {
    dateElem.value.clearValue()
    globalStore.setPropertyValue(props.property.id, props.image, undefined)
}

function updateInternal(date) {
    if(date == null) return
    if(String(localValue.value) != String(date)) {
        localValue.value = date
    }
}

onMounted(() => {
    localValue.value = propRef.value.value
})

watch(propRef, () => localValue.value = propRef.value.value)

</script>

<template>
    <VueDatePicker v-model="localValue" :teleport="true" input-class-name="custom-date-picker" :hide-input-icon="true" @internal-model-change="updateInternal"
        calendar-cell-class-name="custom-date-picker" :inline="false" ref="dateElem">
        <template #action-buttons>
            <span style="font-size: 13px;" class="text-nowrap">
                <span class="base-btn me-1" @click="clear"><i class="bi bi-trash" /></span>
                <span class="base-btn me-1 border" @click="cancel">cancel</span>
                <span v-if="(localValue != undefined && localValue != '')" class="me-1 base-btn border" @click="save">save</span>
            </span>
        </template>
    </VueDatePicker>
</template>
