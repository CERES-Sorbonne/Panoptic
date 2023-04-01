<script setup lang="ts">
import {computed} from 'vue'
import { globalStore } from '@/data/store';
import { Image, Property, PropertyRef } from '@/data/models';
import PropertyInput from '../inputs/PropertyInput.vue';

const props = defineProps({
    image: Object as () => Image,
    width: {type: Number, default: 100}
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

</script>

<template>
    <div class="d-inline-block overflow-hidden" :style="'width: ' + props.width + 'px;'">
        <img :src="props.image.url" :style="'width: ' + props.width + 'px;'" />
        <div class="" v-for="property in imageProperties">
            <PropertyInput :property="property" />
        </div>
        <!-- <input class="small form-control" /> -->
    </div>
</template>

<style>
.small-text {
    font-size: 14px;
}

</style>