<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import PropertyDropdown from '../properties/PropertyDropdown.vue';
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()

const props = defineProps<{
    modelValue: any
    type: string
    label?: string,
    desc?: string
}>();

defineExpose({ focus })

const emits = defineEmits(['update:modelValue']);

const elem = ref(null)
const localValue = ref(props.modelValue)
const defaultProperty = ref(data.propertyList[0])
function focus() {
    // console.log('focus', elem.value)
    if (elem.value) {
        elem.value.focus()
    }
}

watch(() => props.modelValue, () => localValue.value = props.modelValue)
watch(localValue, () => {
    if (props.type == 'property' && localValue.value in data.properties) {
        defaultProperty.value = data.properties[localValue.value]
    }

    if (localValue.value != props.modelValue) {
        let toSend = localValue.value
        if (localValue.value == '' || localValue.value == false) {
            toSend = undefined
        }
        emits('update:modelValue', toSend)
    }
})

onMounted(() => {
    if (props.type == 'property' && props.modelValue == undefined) {
        localValue.value = data.propertyList[0]?.id
    }
    if (props.type == 'property' && localValue.value in data.properties) {
        defaultProperty.value = data.properties[localValue.value]
    }

})
</script>

<template>
    <wTT :message="props.desc">
        <div class="d-flex">
            <div v-if="props.label" class="me-1">{{ props.label }}</div>
            <!-- <div class="me-1">[{{ props.type }}]</div> -->
            <div v-if="props.type == 'str'">
                <input type="text" v-model="localValue" ref="elem" />
            </div>
            <div v-if="props.type == 'int'">
                <input type="number" step="1" v-model="localValue" ref="elem" />
            </div>
            <div v-if="props.type == 'float'">
                <input type="number" v-model="localValue" ref="elem" />
            </div>
            <div v-if="props.type == 'bool'">
                <input type="checkbox" v-model="localValue" ref="elem" />
            </div>
            <div v-if="props.type == 'property'">
                <div v-if="!data.propertyList.length" class="disabled rounded ps-1 pe-1">Create Property First</div>
                <PropertyDropdown v-else v-model="defaultProperty"
                    @update:model-value="localValue = defaultProperty.id" />
            </div>
        </div>
    </wTT>
</template>

<style scoped>
input {
    font-size: 14px;
    line-height: 12px;
    padding: 2px 4px !important;
    border: 1px solid var(--border-color);
    border-radius: 3px;
}
</style>