<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import PropertyInput from '@/components/inputs/PropertyInput.vue';
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

const panoptic = usePanopticStore()
const store = useProjectStore()

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

const image = computed(() => props.image.image)

const containerElem = ref(null)
const hover = ref(false)

function hasProperty(propertyId: number) {
    return image.value.properties[propertyId] && image.value.properties[propertyId].value !== undefined
}

const imageProperties = computed(() => {
    let res: Array<PropertyRef> = []
    props.properties.forEach((p: Property) => {
        let propRef: PropertyRef = {
            propertyId: p.id,
            type: p.type,
            value: hasProperty(p.id) ? image.value.properties[p.id].value : undefined,
            imageId: image.value.id,
            mode: p.mode
        }
        res.push(propRef)

    });
    return res
})

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
            <div :style="imageContainerStyle" class="img-container" @click="panoptic.showModal(ModalId.IMAGE, props.image)"
                @mouseenter="hover = true" @mouseleave="hover = false">
                <div v-if="props.score != undefined" class="simi-ratio">{{ Math.floor(props.score * 100) }}</div>
                <img :src="props.size < 150 ? image.url : image.fullUrl" :style="imageStyle" />

                <div v-if="hover || props.selected" class="w-100 box-shadow" :style="imageContainerStyle"></div>
                <SelectCircle v-if="hover || props.selected" :model-value="props.selected"
                    @update:model-value="v => emits('update:selected', v)" class="select" :light-mode="true" />
            </div>
        </Zoomable>

        <wTT v-if="props.image.sha1Group && props.image.sha1Group.images.length > 1" message="main.view.instances_tooltip"
            :click="false">
            <div class="image-count">{{ props.image.sha1Group.images.length }}</div>
        </wTT>
        <div class="prop-container" v-if="imageProperties.length > 0 && !props.hideProperties">
            <div v-for="property, index in imageProperties">
                <div class="custom-hr ms-2 me-2" v-if="index > 0"></div>
                <!-- <TagInput v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag"
                    :property="property" :max-size="String(props.size)" :mono-tag="property.type == PropertyType.tag"
                    :input-id="[...props.groupId.split('-').map(Number), property.propertyId, props.index]" /> -->
                <div v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag" class="d-flex"
                    style="padding-top: 4px; padding-bottom: 4px;">
                    <PropertyIcon :type="property.type" style="margin-right: 2px;" />
                    <TagPropInputDropdown :property="store.data.properties[property.propertyId]" :image="image"
                        :can-create="true" :can-customize="true" :can-link="true" :can-delete="true" :auto-focus="true"
                        :no-wrap="true" :width="(width - 22)" :teleport="true" />
                </div>
                <div v-else-if="property.type == PropertyType.color" class="d-flex flex-row">
                    <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
                    <ColorPropInput class="mt-1 ms-0" :rounded="true" :image="image"
                        :property="store.data.properties[property.propertyId]" :width="width - 22" :min-height="20" />
                </div>
                <div v-else-if="property.type == PropertyType.string" class="d-flex flex-row">
                    <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
                    <TextInput :property="store.data.properties[property.propertyId]" :image="image" :width="width - 22"
                        :height="26" />
                </div>
                <div v-else-if="property.type == PropertyType.number" class="d-flex flex-row">
                    <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
                    <TextInput :property="store.data.properties[property.propertyId]" :image="image" :width="width - 22"
                        :height="26" :no-nl="true" />
                </div>
                <div v-else-if="property.type == PropertyType.url" class="d-flex flex-row">
                    <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
                    <TextInput :property="store.data.properties[property.propertyId]" :image="image" :width="width - 22"
                        :height="26" :no-nl="true" />
                </div>
                <div v-else-if="property.type == PropertyType.checkbox" class="d-flex flex-row overflow-hidden">
                    <CheckboxPropInput :property="store.data.properties[property.propertyId]" :image="image"
                        :width="width - 22" :min-height="26" />
                    <div style="line-height: 26px; margin-left: 4px;">{{ store.data.properties[property.propertyId].name }}
                    </div>
                </div>
                <div v-else-if="property.type == PropertyType.date" class="d-flex flex-row" style="padding-top: 1px;">
                    <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
                    <DateInput :property="store.data.properties[property.propertyId]" :image="image" :width="width - 22"
                        style="line-height: 25px;" />
                </div>
                <PropertyInput v-else :property="property" :max-size="String(props.size)"
                    :input-id="[...props.groupId.split('-').map(Number), property.propertyId, props.index]"
                    style="line-height: 26px;" />
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