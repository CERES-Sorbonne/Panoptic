<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import PropertyDropdown from '../properties/PropertyDropdown.vue';
import { useDataStore } from '@/data/dataStore';
import { ParamDescription } from '@/data/models';

const data = useDataStore()

const props = defineProps<{
    input: ParamDescription
}>();

defineExpose({ focus })

const emits = defineEmits(['update:modelValue']);

const elem = ref(null)
const localValue = ref(props.input.defaultValue)
const defaultProperty = ref(data.propertyList[0])
function focus() {
    // console.log('focus', elem.value)
    if (elem.value) {
        elem.value.focus()
    }
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

onMounted(() => {
    if (props.input.type == 'property' && props.input.defaultValue == undefined) {
        localValue.value = data.propertyList[0]?.id
    }
    if (props.input.type == 'property' && localValue.value in data.properties) {
        defaultProperty.value = data.properties[localValue.value]
    }
    if(props.input.type == 'enum' && props.input.possibleValues.indexOf(props.input.defaultValue) < 0) {
        localValue.value = props.input.possibleValues[0]
    }
    if(props.input.type == 'enum' && props.input.defaultValue == undefined) {
        localValue.value = props.input.possibleValues[0]
    }

})
</script>

<template>
    <wTT :message="props.input.description">
        <div class="d-flex">
            <div v-if="props.input.name" class="me-1">{{ props.input.name }}</div>
            <!-- <div class="me-1">[{{ props.input.type }}]</div> -->
            <div v-if="props.input.type == 'str'">
                <input type="text" v-model="localValue" ref="elem" />
            </div>
            <div v-if="props.input.type == 'int'">
                <input type="number" step="1" v-model="localValue" ref="elem" />
            </div>
            <div v-if="props.input.type == 'float'">
                <input type="number" v-model="localValue" ref="elem" />
            </div>
            <div v-if="props.input.type == 'bool'">
                <input type="checkbox" v-model="localValue" ref="elem" />
            </div>
            <div v-if="props.input.type == 'property'">
                <div v-if="!data.propertyList.length" class="disabled rounded ps-1 pe-1">Create Property First</div>
                <PropertyDropdown v-else v-model="defaultProperty"
                    @update:model-value="localValue = defaultProperty.id" />
            </div>
            <div v-if="props.input.type == 'enum'">
                <select v-model="localValue">
                    <option v-for="v in props.input.possibleValues" :value="v">{{ v }}</option>
                </select>
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