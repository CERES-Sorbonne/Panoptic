<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { globalStore } from '@/data/store';
import { Image, Modals, Property, PropertyRef, PropertyType } from '@/data/models';
import PropertyInput from '../inputs/PropertyInput.vue';
import TagInput from '../inputs/TagInput.vue';

const props = defineProps({
    image: Object as () => Image,
    size: { type: Number, default: 100 },
    index: Number,
    groupId: String,
    hideProperties: Boolean,
    constraintWidth: Boolean,
    noBorder: Boolean
})

const emits = defineEmits(['resize'])

const containerElem = ref(null)
// const properties = computed(() => globalStore.propertyList.filter((p: any) => p.show))

function hasProperty(propertyId: number) {
    return props.image.properties[propertyId] && props.image.properties[propertyId].value !== undefined
}

const imageProperties = computed(() => {

    let selected = globalStore.tabs[globalStore.selectedTab].data.visibleProperties

    let res: Array<PropertyRef> = []
    globalStore.propertyList.forEach((p: Property) => {
        if (selected[p.id]) {
            let propRef: PropertyRef = {
                propertyId: p.id,
                type: p.type,
                value: hasProperty(p.id) ? props.image.properties[p.id].value : undefined,
                imageId: props.image.id,
                mode: p.mode
            }
            res.push(propRef)
        }

    });
    return res
})

const imageWidthStyle = computed(() => `max-width: ${Number(props.size) - 4}px; max-height: ${Number(props.size) - 4}px;`)

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

    let ratio = props.image.height / props.image.width

    let w = props.size
    let h = w * ratio

    if (ratio > 2) {
        h = props.size * 2
        w = h / ratio
    }

    const res = { width: w, height: h }
    emits('resize', res)
    return res

})

const imageContainerStyle = computed(() => `width: ${imageSizes.value.width - 2}px; height: ${props.size}px;`)
const imageStyle = computed(() => `width: ${imageSizes.value.width - 2}px; height: ${imageSizes.value.height}px;`)
const widthStyle = computed(() => `width: ${Math.max(Number(props.size), imageSizes.value.width)}px;`)
</script>

<template>
    <div class="full-container" :style="widthStyle" :class="(!props.noBorder ? 'img-border' : '')" ref="containerElem">
        <!-- {{ props.image.containerRatio }} -->
        <div :style="imageContainerStyle" class="img-container" @click="globalStore.showModal(Modals.IMAGE, props.image)">
            <img :src="props.size < 150 ? props.image.url : props.image.fullUrl" :style="imageStyle" />
        </div>
        <div class="prop-container" v-if="imageProperties.length > 0 && !props.hideProperties">
            <div v-for="property, index in imageProperties">
                <div class="custom-hr ms-2 me-2" v-if="index > 0"></div>
                <TagInput v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag"
                    :property="property" :max-size="String(props.size)" :mono-tag="property.type == PropertyType.tag"
                    :input-id="[...props.groupId.split('-').map(Number), property.propertyId, props.index]" />
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
</style>