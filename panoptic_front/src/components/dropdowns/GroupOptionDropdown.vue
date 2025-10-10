<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import Dropdown from './Dropdown.vue';
import TimeUnitDropdown from './TimeUnitDropdown.vue';
import { GroupOption } from '@/core/GroupManager';
import { DateUnit } from '@/data/models';

const props = defineProps<{
    option: GroupOption
}>()

const emits = defineEmits<{
    'change': [option: GroupOption]
}>()

const value = ref(1)
const unit = ref(DateUnit.Year)

function onHide() {
    if(props.option.stepSize == value.value && props.option.stepUnit == unit.value) {
        return
    }
    emits('change', { stepSize: value.value, stepUnit: unit.value })
}

function updateLocal() {
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
                <div class="d-flex ipt">
                    <div><input type="number" v-model="value" /></div>
                    <div class="ms-2" min="1">
                        <TimeUnitDropdown v-model="unit" @hide="focus" />
                    </div>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>

.ipt {
    padding: 5px;
}

input[type="number"] {
    width: 40px;
    font-size: 15px !important;
}
</style>