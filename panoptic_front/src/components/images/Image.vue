<script setup lang="ts">
import {computed} from 'vue'
import { globalStore } from '@/data/store';
import { Image, Modals, Property, PropertyRef, PropertyType } from '@/data/models';
import PropertyInput from '../inputs/PropertyInput.vue';
import TagInput from '../inputs/TagInput.vue';

const props = defineProps({
    image: Object as () => Image,
    width: {type: String, default: '100'},
    index: Number
})

const properties = computed(() => globalStore.propertyList.filter((p:any) => p.show))

function hasProperty(propertyId: number) {
    return props.image.properties[propertyId] && props.image.properties[propertyId].value !== undefined
}

const imageProperties = computed(() => {
    let res: Array<PropertyRef> = []
    properties.value.forEach((p: Property) => {
        let propRef: PropertyRef = {
            propertyId: p.id,
            type: p.type,
            value: hasProperty(p.id) ? props.image.properties[p.id].value : undefined,
            imageSHA1: props.image.sha1
        }
        res.push(propRef)
    });
    return res
})

const widthStyle = computed(() => `width: ${Number(props.width)}px;`)
const imageWidthStyle = computed(() => `width: ${Number(props.width) -4}px; max-height: ${Number(props.width) -4}px`)

</script>

<template>
    <div class="d-inline-block small-text m-2" :style="widthStyle">
        <img :src="props.image.url" :style="imageWidthStyle" @click="globalStore.showModal(Modals.IMAGE, props.image)"/>
        <div v-for="property in imageProperties" class="" :style="imageWidthStyle">
            <TagInput v-if="property.type == PropertyType.multi_tags" :property="property" :max-size="props.width" :input-id="[property.propertyId, props.index]"/>
            <TagInput v-else-if="property.type == PropertyType.tag" :property="property" :max-size="props.width" :mono-tag="true" :input-id="[property.propertyId, props.index]"/>
            <PropertyInput v-else :property="property" :max-size="props.width" :input-id="[property.propertyId, props.index]"/>
        </div>
    </div>
</template>

<style>
.small-text {
    font-size: 14px;
}

</style>