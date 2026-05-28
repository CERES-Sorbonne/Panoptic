<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import wTT from '../../tooltips/withToolTip.vue'
import { ImageIterator } from '@/core/GroupManager'
import { ModalId, Property } from '@/data/models'
import { usePanopticStore } from '@/data/panopticStore'
import Zoomable from '@/components/Zoomable.vue'
import CenteredImage from '@/components/images/CenteredImage.vue'
import TreePropertyInput from './TreePropertyInput.vue'
import { useColumnStore, META } from '@/data/dataStore2'

const panoptic = usePanopticStore()
const store    = useColumnStore()

const props = defineProps({
    image: ImageIterator,
    size: { type: Number, default: 100 },
    index: Number,
    groupId: Number,
    hideProperties: Boolean,
    constraintWidth: Boolean,
    noBorder: Boolean,
    properties: Array<Property>,
    selectedPreview: Boolean
})

const emits = defineEmits(['resize', 'update:selected'])

// Read from the shared reactive instances map registered by the parent TreeScroller.
// Falls back to an empty-properties stub so template expressions never throw.
const inst = computed(() =>
    store.instances[props.image.image.id] ?? { id: props.image.image.id, properties: {} }
)

const isSelected = computed(() => {
    const slot = store.slotMap.get(props.image.image.id)
    return slot !== undefined && store.isSelected(slot)
})

function getSizes(width: number, height: number) {
    if (!width || !height) return { width: props.size, height: props.size }
    const ratio = width / height
    let h = props.size
    let w = h * ratio
    if (ratio > 2) {
        w = props.size * 2
        h = w / ratio
    }
    return { width: w, height: h }
}

function instSizes(inst: { properties: Record<number, any> }) {
    return getSizes(inst.properties[META.WIDTH], inst.properties[META.HEIGHT])
}

function instWidth(inst: { properties: Record<number, any> }) {
    return Math.max(instSizes(inst).width, props.size)
}

const hover    = ref(false)
const hideImg  = inject('hideImg')
const inputKey = inject('inputKey') as string

const score = computed(() => {
    const group = props.image.group
    if (!group.scores) return undefined
    return group.scores.valueIndex[props.image.image.id]
})
</script>

<template>
    <div
        class="full-container"
        :class="(!props.noBorder ? 'img-border' : '')"
        :style="`width: ${instWidth(inst) + 2}px;`"
    >
        <Zoomable v-if="!hideImg" :image="props.image.image">
            <div
                class="img-container"
                :style="`width: ${instWidth(inst) + 2}px; height: ${props.size}px;`"
                @click="panoptic.showModal(ModalId.IMAGE, props.image)"
                @mouseenter="hover = true"
                @mouseleave="hover = false"
            >
                <div v-if="score != undefined" class="simi-ratio">{{ score }}</div>

                <CenteredImage
                    :sha1="inst.properties[META.SHA1]"
                    :image-width="inst.properties[META.WIDTH]"
                    :image-height="inst.properties[META.HEIGHT]"
                    :width="instWidth(inst)"
                    :height="props.size"
                    style="position: absolute; top: 0"
                />

                <div v-if="hover || isSelected" class="w-100 box-shadow"
                    :style="`width: ${instWidth(inst) + 2}px; height: ${props.size}px;`" />
                <SelectCircle
                    v-if="hover || isSelected"
                    :model-value="isSelected"
                    @update:model-value="v => emits('update:selected', v)"
                    class="select"
                    :light-mode="true"
                />
            </div>
        </Zoomable>

        <wTT v-if="props.image.sha1Group && props.image.sha1Group.images.length > 1"
            message="main.view.instances_tooltip" :click="false">
            <div class="image-count">{{ props.image.sha1Group.images.length }}</div>
        </wTT>

        <div class="prop-container" v-if="props.properties.length && !props.hideProperties">
            <div v-for="property, index in props.properties" :key="property.id">
                <div class="custom-hr ms-2 me-2" v-if="index > 0"></div>
                <TreePropertyInput
                    :group-id="props.image.groupId"
                    :input-key="inputKey"
                    :property="property"
                    :instance="inst"
                    :width="instWidth(inst)"
                    :idx="props.image.getImageOrder()"
                />
            </div>
        </div>

        <div v-if="props.selectedPreview" class="w-100 h-100"
            style="position: absolute; top: 0; left: 0; background-color: rgba(0, 0, 255, 0.127);" />
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
    background-color: white;
    margin-bottom: 7px;
    margin-right: 7px;
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
