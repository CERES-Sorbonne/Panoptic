<script setup lang="ts">
import { Image, Property, PropertyType } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import TextInput from './TextInput.vue';
import { globalStore } from '@/data/store';

const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Image,
    noNl: {
        type: Boolean,
        default: false,
    },
    width: Number,
    minHeight: { type: Number, default: 30 },
    urlMode: Boolean,
    autoFocus: Boolean,
    noShadow: Boolean,
    alwaysShadow: Boolean,
    blurOnEnter:  {type: Boolean, default: true}

})
const emits = defineEmits({ 'update:height': Number, 'save': undefined })

const localValue = ref('')
const elem = ref(null)
// const inputElem = computed(() => elem.value.inputElem)

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))
const isFocus = computed(() => elem.value?.isFocus)

function focus() {
    elem.value.focus()
}

function updateFromStore() {
    localValue.value = propRef.value.value ?? ''
}

function save() {
    emits('save')
    if (!propRef.value.value && localValue.value == '') return
    if (propRef.value.value == localValue.value) return

    // console.log(propRef.value.value, localValue.value)
    globalStore.setPropertyValue(props.property.id, props.image, localValue.value)

}


onMounted(updateFromStore)
onMounted(async () => {
    if(props.autoFocus) {
        await nextTick()
        focus()
    }
})
// watch(propRef, updateFromStore)


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
    <div class="container2" :style="{ minHeight: (props.minHeight - 4) + 'px' }">
        <TextInput class="container2" :editable="true" tag="div" :no-html="true" v-model="localValue"
            :width="props.width" @update:height="h => emits('update:height', h)" ref="elem" :min-height="props.minHeight"
            :no-nl="props.noNl" :url-mode="props.urlMode" @blur="save" :only-number="property.type == PropertyType.number" :no-shadow="props.noShadow" :always-shadow="props.alwaysShadow" :blur-on-enter="props.blurOnEnter"/>
    </div>
</template>

<style scoped>
.container2 {
    padding: 0;
    margin: 0;
}
</style>
