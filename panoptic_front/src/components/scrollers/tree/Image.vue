<script setup lang="ts">
import { computed, ref, triggerRef, watch } from 'vue'
import ColorPropInput from '@/components/inputs/ColorPropInput.vue';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import TextInput from '@/components/inputs/monoline/TextInput.vue';
import CheckboxPropInput from '@/components/inputs/CheckboxPropInput.vue';
import wTT from '../../tooltips/withToolTip.vue'
import DateInput from '@/components/inputs/monoline/DateInput.vue';
import TagPropInputDropdown from '@/components/tags/TagPropInputDropdown.vue';
import { Group, ImageIterator } from '@/core/GroupManager';
import { useProjectStore } from '@/data/projectStore';
import { ModalId, Property, PropertyRef, PropertyType, Image } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { keyState } from '@/data/keyState';
import { zoomModal } from '@/components/modals/zoomModal';
import Zoomable from '@/components/Zoomable.vue';
import { useDataStore } from '@/data/dataStore';
import PropInput from './PropInput.vue';

const panoptic = usePanopticStore()
const store = useProjectStore()
const data = useDataStore()


const props = defineProps({
    image: ImageIterator,
    score: Number,
    size: { type: Number, default: 100 },
    index: Number,
    groupId: String,
    hideProperties: Boolean,
    constraintWidth: Boolean,
    noBorder: Boolean,
    properties: Array<Property>,
    selected: Boolean,
    selectedPreview: Boolean
})

const emits = defineEmits(['resize', 'update:selected'])

const instance = computed(() => Object.assign({}, data.instances[props.image.image.id]))
const image = computed(() => instance.value)

const containerElem = ref(null)
const hover = ref(false)


const imageSizes = computed(() => {
    let ratio = image.value.width / image.value.height

    let h = props.size
    let w = h * ratio

    if (ratio > 2) {
        w = props.size * 2
        h = w / ratio
    }

    return { width: w, height: h }
})

const imageContainerStyle = computed(() => `width: ${Math.max(imageSizes.value.width, props.size) - 2}px; height: ${props.size}px;`)
const imageStyle = computed(() => `width: ${imageSizes.value.width - 2}px; height: ${imageSizes.value.height}px;`)
const width = computed(() => Math.max(Number(props.size), imageSizes.value.width))
const widthStyle = computed(() => `width: ${Math.max(Number(props.size), imageSizes.value.width)}px;`)

</script>

<template>
    <div class="full-container" :style="widthStyle" :class="(!props.noBorder ? 'img-border' : '')" ref="containerElem">
        <!-- {{ props.image.containerRatio }} -->
        <Zoomable :image="props.image.image">
            <div :style="imageContainerStyle" class="img-container"
                @click="panoptic.showModal(ModalId.IMAGE, props.image)" @mouseenter="hover = true"
                @mouseleave="hover = false">
                <div v-if="props.score != undefined" class="simi-ratio">{{ Math.floor(props.score * 100) }}</div>
                <img :src="props.size < 150 ? image.url : image.fullUrl" :style="imageStyle" />

                <div v-if="hover || props.selected" class="w-100 box-shadow" :style="imageContainerStyle"></div>
                <SelectCircle v-if="hover || props.selected" :model-value="props.selected"
                    @update:model-value="v => emits('update:selected', v)" class="select" :light-mode="true" />
            </div>
        </Zoomable>

        <wTT v-if="props.image.sha1Group && props.image.sha1Group.images.length > 1"
            message="main.view.instances_tooltip" :click="false">
            <div class="image-count">{{ props.image.sha1Group.images.length }}</div>
        </wTT>
        <div class="prop-container" v-if="props.properties.length && !props.hideProperties">
            <div v-for="property, index in props.properties">
                <div class="custom-hr ms-2 me-2" v-if="index > 0"></div>
                <PropInput :property="property" :image="instance" :size="width" />
            </div>
        </div>
        <div v-if="props.selectedPreview" class="w-100 h-100"
            style="position: absolute; top:0; left: 0; background-color: rgba(0, 0, 255, 0.127);"></div>
    </div>
</template>

<style scoped>
.image-count {
    position: absolute;
    top: 0;
    right: 0;
    padding: 0px 4px;
    background-color: var(--border-color);
    color: var(--grey-text);
    font-size: 10px;
    line-height: 15px;
    margin: 2px;
    border-radius: 5px;
    z-index: 100;
}

.simi-ratio {
    position: absolute;
    bottom: 0;
    right: 0;
    padding: 0px 4px;
    background-color: var(--border-color);
    color: var(--grey-text);
    font-size: 10px;
    line-height: 15px;
    margin: 2px;
    border-radius: 5px;
    z-index: 100;
}

.full-container {
    position: relative;
}

.img-border {
    border: 1px solid var(--border-color);
}

.img-container {
    position: relative;
    margin: auto;
    padding: auto;
    cursor: pointer;
}

.prop-container {
    width: 100%;
    border-top: 1px solid var(--border-color);
    padding: 2px;
    padding-top: 0px;
    padding-bottom: 0px;
    font-size: 12px;
}

img {
    max-height: 100%;
    max-width: 100%;
    /* width: auto;
    height: auto; */
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    margin: auto;
}

.select {
    position: absolute;
    top: 0;
    left: 5px;
}

.box-shadow {
    position: relative;
}

.box-shadow::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    -webkit-box-shadow: inset 0px 24px 25px -20px rgba(0, 0, 0, 0.3);
    -moz-box-shadow: inset 0px 24px 25px -20px rgba(0, 0, 0, 0.3);
    box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    overflow: hidden;
}
</style>