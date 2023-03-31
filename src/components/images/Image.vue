<script setup lang="ts">
import {computed} from 'vue'
import { globalStore } from '@/data/store';
import { Image } from '@/data/models';
import PropertyInput from '../inputs/PropertyInput.vue';

const props = defineProps({
    image: Object as () => Image,
    width: {type: Number, default: 100}
})

const properties = computed(() => globalStore.propertyList.filter((p:any) => p.show))

</script>

<template>
    <div class="d-inline-block bg-warning overflow-hidden" :style="'width: ' + props.width + 'px;'">
        <img :src="props.image.url" :style="'width: ' + props.width + 'px;'" />
        <div class="" v-for="property in properties">
            <PropertyInput :property="props.image.properties[property.id]" />
        </div>
        <!-- <input class="small form-control" /> -->
    </div>
</template>

<style>
.small-text {
    font-size: 14px;
}

</style>