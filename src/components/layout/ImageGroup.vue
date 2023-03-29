<script setup>
import {computed} from 'vue'
import ExpandOption from '../menu/ExpandOption.vue';

const props = defineProps({
    group: Object,
    small: String
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
                <div class="row ms-3">
                    <img :src="image.url" style="width: 100px;" v-for="image in images"/>
                </div>
            </div>
            <div v-else-if="hasSubgroups" class="ms-3">
                <ImageGroup v-for="group in subgroups" :group="group" small=true />
            </div>
            <div v-else>
                Error.. No Subgroups, No images, Why ?
            </div>
        </template>
    </ExpandOption>
</template>