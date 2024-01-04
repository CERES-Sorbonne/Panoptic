<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import Dropdown from './Dropdown.vue';
import TimeUnitDropdown from './TimeUnitDropdown.vue';
import { GroupOption } from '@/core/GroupManager';

const props = defineProps<{
    option: GroupOption
}>()

const emits = defineEmits<{
    'change': [option: GroupOption]
}>()

const isSet = ref(true)
const value = ref(1)
const unit = ref(undefined)

function onHide() {
    if(props.option.useSteps == isSet.value && props.option.stepSize == value.value && props.option.stepUnit == unit.value) {
        return
    }
    emits('change', { useSteps: isSet.value, stepSize: value.value, stepUnit: unit.value })
}

function updateLocal() {
    isSet.value = props.option.useSteps
    value.value = props.option.stepSize ?? 1
    unit.value = props.option.stepUnit
}

watch(() => props.option, updateLocal)
onMounted(updateLocal)

watch(value, () => {
    if (value.value < 1 || value.value == undefined || isNaN(value.value)) {
        value.value = 1
    }
})

</script>

<template>
    <Dropdown @hide="onHide">
        <template #button><i class="bi bi-three-dots-vertical"></i></template>
        <template #popup="{ hide, focus }">
            <div class="">
                <div class="set-box"><input type="checkbox" v-model="isSet" /> Set granularity</div>
                <div class="d-flex ipt" :class="isSet ? '' : 'grey-out'">
                    <div><input type="number" :disabled="!isSet" v-model="value" /></div>
                    <div class="ms-2" min="1">
                        <TimeUnitDropdown v-model="unit" @hide="focus" />
                    </div>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.grey-out {
    background-color: rgb(240, 240, 240);
    color: rgb(90, 90, 90);
}

.set-box {
    padding: 5px 5px 2px 5px;
    border-bottom: 1px solid var(--border-color);
}

.ipt {
    padding: 5px;
}

input[type="number"] {
    width: 40px;
    font-size: 15px !important;
}
</style>