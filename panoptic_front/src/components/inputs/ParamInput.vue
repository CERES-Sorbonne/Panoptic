// ParamInput.vue
<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import PropertyDropdown from '../properties/PropertyDropdown.vue';
import { useDataStore } from '@/data/dataStore';
import { ParamDescription, VectorType } from '@/data/models';
import VectorTypeDropdown from '../dropdowns/VectorTypeDropdown.vue';

const data = useDataStore()

const props = defineProps<{
    input: ParamDescription
    source: string
    maxWidth?: number
}>();

defineExpose({ focus })

const emits = defineEmits(['update:modelValue']);

const elem = ref(null)
const localValue = ref(props.input.defaultValue)
console.log(props.input.defaultValue)
const defaultProperty = ref(data.propertyList[0])
function focus() {
    // console.log('focus', elem.value)
    if (elem.value) {
        elem.value.focus()
    }
}

function initValues() {
    localValue.value = props.input.defaultValue
}

function vectorName(vectorType: VectorType) {
    return '' + vectorType.id + ' ' + vectorType.source + '.' + Object.keys(vectorType.params).filter(k => vectorType.params[k]).map(k => k + '_' + vectorType.params[k]).join('_')
}

function setFile(event: Event){
    localValue.value = (<HTMLInputElement>event.target).files[0]
}

watch(() => props.input.defaultValue, () => localValue.value = props.input.defaultValue)
watch(localValue, () => {
    if (props.input.type == 'property' && localValue.value in data.properties) {
        defaultProperty.value = data.properties[localValue.value]
    }

    if (localValue.value != props.input.defaultValue) {
        let toSend = localValue.value
        if (localValue.value == '' || localValue.value == false) {
            toSend = undefined
        }
        props.input.defaultValue = localValue.value
    }
})

watch(props, initValues)


onMounted(initValues)
</script>

<template>
    <wTT :message="props.input.description" class="label-cell">
        <div v-if="props.input.name" class="param-label">{{ props.input.name }}</div>
    </wTT>
    
    <div class="input-cell">
        <div v-if="props.input.type == 'str'">
            <input type="text" v-model="localValue" ref="elem" :style="{width: props.maxWidth+'px'}"/>
        </div>
        <div v-if="props.input.type == 'int'">
            <input type="number" step="1" v-model="localValue" ref="elem" :style="{width: props.maxWidth+'px'}"/>
        </div>
        <div v-if="props.input.type == 'float'">
            <input type="number" v-model="localValue" ref="elem" :style="{width: props.maxWidth+'px'}"/>
        </div>
        <div v-if="props.input.type == 'bool'">
            <input type="checkbox" v-model="localValue" ref="elem" :style="{width: props.maxWidth+'px'}"/>
        </div>
        <div v-if="props.input.type == 'property'" :style="{width: props.maxWidth+'px'}">
            <div v-if="!data.propertyList.length" class="disabled rounded ps-1 pe-1">Create Property First</div>
            <PropertyDropdown v-else v-model="defaultProperty"
                @update:model-value="localValue = defaultProperty.id" />
        </div>
        <div v-if="props.input.type == 'enum'" :style="{width: props.maxWidth+'px'}">
            <select v-model="localValue">
                <option v-for="v in props.input.possibleValues" :value="v">{{ v }}</option>
            </select>
        </div>
        <div v-if="props.input.type == 'vector_type'">
            <VectorTypeDropdown v-model="localValue" :width="props.maxWidth-6" />
            <!-- <select v-model="localValue" style="max-width: 200px;">
                <option v-for="v in data.vectorTypes" :value="v">{{ vectorName(v) }}</option>
            </select> -->
        </div>

        <div v-if="props.input.type == 'own_vector_type'">
            <VectorTypeDropdown v-model="localValue" :source="props.source" :width="props.maxWidth-6"/>
            <!-- <select v-model="localValue" style="max-width: 200px;">
                <option v-for="v in data.vectorTypes.filter(v => v.source == props.source)" :value="v">{{
                    vectorName(v) }}</option>
            </select> -->
        </div>
    </div>
</template>

<style scoped>
.param-row {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0px;
    align-items: center;
}

.label-cell {
    display: flex;
    width: 100%;
}

.label-cell > * {
    width: 100%;
}

.param-label {
    width: 100%;
    text-align: left;
}

.param-label {
    white-space: nowrap;
}

.input-cell {
    display: flex;
    align-items: center;
}

input {
    font-size: 14px !important;
    line-height: 12px;
    padding: 2px 4px !important;
    border: 1px solid var(--border-color);
    border-radius: 3px;
}
</style>