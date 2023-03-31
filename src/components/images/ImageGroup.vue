<script setup>
import {computed} from 'vue'
import ExpandOption from '../menu/ExpandOption.vue';
import Image from './Image.vue';

const props = defineProps({
    group: Object,
    small: String,
    imageSize: Number
})

const images = computed(() => props.group.images)
const subgroups = computed(() => props.group.groups)
const hasImages = computed(() => images.value.length > 0)
const hasSubgroups = computed(() => subgroups.value != undefined)

function recursiveCount(groupe) {
    if(groupe.groups) {
        return props.group.groups.map(recursiveCount).reduce((a, b) => a+b, 0)
    }
    else {
        return groupe.images.length
    }
}

const imageSum = computed(() => {
    if(!hasImages.value && !hasSubgroups.value) {
        return 0
    }
    return recursiveCount(props.group)

})
</script>

<template>
    <ExpandOption :small="props.small" :left-align="true">
        <template #name>{{ props.group.name }} ({{ imageSum }})<i class="h5 ms-2 bi bi-share"></i></template>
        <template #content>
            <div  v-if="hasImages">
                <div class="ms-3">
                    <Image :image="image" :width="props.imageSize" v-for="image in images" class="me-1"/>
                </div>
            </div>
            <div v-else-if="hasSubgroups" class="ms-3">
                <ImageGroup v-for="group in subgroups" :group="group" small=true :image-size="props.imageSize" />
            </div>
            <div v-else>
                Error.. No Subgroups, No images, Why ?
            </div>
        </template>
    </ExpandOption>
</template>