<script setup lang="ts">
import { Instance, Property, PropertyType } from '@/data/models';
import { computed, nextTick, onMounted, ref, watch, withDefaults } from 'vue';
import TextInput from './TextInput.vue';
import { useProjectStore } from '@/data/projectStore'
import { useDataStore } from '@/data/dataStore';

const project = useProjectStore()
const data = useDataStore()

const props = withDefaults(defineProps<{
    property: Property
    image: Instance
    noNl?: boolean
    width: number
    minHeight: number
    urlMode?: boolean
    autoFocus?: boolean
    noShadow?: boolean
    alwaysShadow?: boolean
    blurOnEnter?: boolean
    edit?: boolean

}>(), {
    blurOnEnter: true,
    minHeight: 30,
    edit: true
})
const emits = defineEmits({ 'update:height': Number, 'save': undefined })

const localValue = ref('')
const storeValue = computed(() => data.instances[props.image.id].properties[props.property.id])
const elem = ref(null)
function focus() {
    elem.value.focus()
}

function updateFromStore() {
    localValue.value = storeValue.value ?? ''
}

function save() {
    emits('save')
    // if (!propRef.value.value && localValue.value == '') return
    if (storeValue.value === localValue.value) return

    // console.log(propRef.value.value, localValue.value)
    project.setPropertyValue(props.property.id, props.image, localValue.value)

}


onMounted(updateFromStore)
onMounted(async () => {
    if(props.autoFocus) {
        await nextTick()
        focus()
    }
})
watch(storeValue, updateFromStore)


defineExpose({
    localValue,
    // inputElem
    focus
})

// watch(localValue, save)

function log(e) {
    console.log(e)
}

</script>

<template>
    <div class="bg-white" style="padding: 0px" :style="{height: props.minHeight - 7 + 'px'}">
        <TextInput class="bg-white" :editable="props.edit" tag="div" :no-html="true" v-model="localValue"
            :width="props.width" @update:height="h => emits('update:height', h)" ref="elem" :min-height="props.minHeight"
            :no-nl="props.noNl" :url-mode="props.urlMode" @blur="save" :only-number="property.type == PropertyType.number" :no-shadow="props.noShadow" :always-shadow="props.alwaysShadow" :blur-on-enter="props.blurOnEnter" />
    </div>
</template>

<style scoped>
.container2 {
    padding: 0;
    margin: 0;
}
</style>
