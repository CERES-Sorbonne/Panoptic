<script setup lang="ts">
import { Instance, Property } from '@/data/models';
import { computed, ref } from 'vue';
import { useProjectStore } from '@/data/projectStore'
import { useDataStore } from '@/data/dataStore';

const project = useProjectStore()
const data = useDataStore()

const props = withDefaults(defineProps<{
    property: Property
    image: Instance
    width: number
    minHeight: number

}>(), {
    minHeight: 30
})
const emits = defineEmits({ 'update:height': Number })

const elem = ref(null)
function focus() {
    elem.value.focus()
}
const propValue = computed(() => data.instances[props.image.id].properties[props.property.id])

function toggle() {
    project.setPropertyValue(props.property.id, props.image, !propValue.value)
}
defineExpose({
    focus
})

</script>

<template>
    <div class="container2 d-flex flex-row" :style="{height: props.minHeight+'px'}">
        <input type="checkbox" v-model="propValue" @click.stop.prevent="toggle"/>
    </div>
</template>

<style scoped>
.container2 {
    padding-left: 0;
    padding-top: 0px;
    margin: 0;

}

input {
    margin-left: 0px;
}

</style>
