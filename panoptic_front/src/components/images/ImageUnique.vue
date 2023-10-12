<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { globalStore } from '@/data/store';
import { Image, Modals, Property, PropertyRef, PropertyType } from '@/data/models';
import PropertyInput from '../inputs/PropertyInput.vue';
import TagInput from '../inputs/TagInput.vue';
import ColorPropInput from '../inputs/ColorPropInput.vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import SelectCircle from '../inputs/SelectCircle.vue';

const props = defineProps({
    image: Object as () => Image,
    size: { type: Number, default: 100 },
    index: Number,
    groupId: String,
    hideProperties: Boolean,
    constraintWidth: Boolean,
    noBorder: Boolean,
    properties: Array<Property>
})

const emits = defineEmits(['resize'])

const containerElem = ref(null)
const hover = ref(false)

function hasProperty(propertyId: number) {
    return props.image.properties[propertyId] && props.image.properties[propertyId].value !== undefined
}

const imageProperties = computed(() => {
    let res: Array<PropertyRef> = []
    props.properties.forEach((p: Property) => {
        let propRef: PropertyRef = {
            propertyId: p.id,
            type: p.type,
            value: hasProperty(p.id) ? props.image.properties[p.id].value : undefined,
            imageId: props.image.id,
            mode: p.mode
        }
        res.push(propRef)

    });
    return res
})

const imageSizes = computed(() => {
    if (!props.constraintWidth) {
        let ratio = props.image.width / props.image.height

        let h = props.size
        let w = h * ratio

        if (ratio > 2) {
            w = props.size * 2
            h = w / ratio
        }

        const res = { width: w, height: h }
        emits('resize', res)
        return res
    }

    return { width: props.size - 4, height: props.size - 4 }
})

const imageContainerStyle = computed(() => `width: ${Math.max(imageSizes.value.width, props.size) - 2}px; height: ${props.size}px;`)
const imageStyle = computed(() => `width: ${imageSizes.value.width - 2}px; height: ${imageSizes.value.height}px;`)
const width = computed(() => Math.max(Number(props.size), imageSizes.value.width))
const widthStyle = computed(() => `width: ${width.value}px;`)
</script>

<template>
    <div class="full-container" :style="widthStyle" :class="(!props.noBorder ? 'img-border' : '')" ref="containerElem">
        <!-- {{ props.image.containerRatio }} -->
        <div :style="imageContainerStyle" class="img-container" @click="globalStore.showModal(Modals.IMAGE, props.image)"
        @mouseenter="hover = true" @mouseleave="hover = false">
            <img :src="props.size < 150 ? props.image.url : props.image.fullUrl" :style="imageStyle" />
            <div v-if="hover" class="w-100 box-shadow" :style="imageContainerStyle"></div>
            <SelectCircle v-show="hover" class="select" :light-mode="true"/>
        </div>
        <div class="prop-container" v-if="imageProperties.length > 0 && !props.hideProperties">
            <div v-for="property, index in imageProperties">
                <div class="custom-hr ms-2 me-2" v-if="index > 0"></div>
                <TagInput v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag"
                    :property="property" :max-size="String(props.size)" :mono-tag="property.type == PropertyType.tag"
                    :input-id="[...props.groupId.split('-').map(Number), property.propertyId, props.index]" />
                <div v-else-if="property.type == PropertyType.color" class="d-flex flex-row">
                    <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
                    <ColorPropInput class="mt-1 ms-0" :rounded="true" :image="props.image"
                        :property="globalStore.properties[property.propertyId]" :width="width - 22" :min-height="20" />
                </div>
                <PropertyInput v-else :property="property" :max-size="String(props.size)"
                    :input-id="[...props.groupId.split('-').map(Number), property.propertyId, props.index]" />
            </div>
        </div>
    </div>
</template>

<style scoped>
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
    -webkit-box-shadow: inset 0px 24px 25px -20px rgba(0,0,0,0.3);
    -moz-box-shadow: inset 0px 24px 25px -20px rgba(0,0,0,0.3);
    box-shadow: inset 0px 50px 30px -30px rgba(0,0,0,0.5);
    overflow: hidden;
}
</style>