<script setup>
import ExpandOption from '../menu/ExpandOption.vue';
import { computed } from 'vue'

const props = defineProps({
    group: Object,
    small: String
})

const images = computed(() => props.group.images)
const subgroups = computed(() => props.group.groups)
const hasImages = computed(() => images.value.length > 0)
const hasSubgroups = computed(() => subgroups.value != undefined)

function recursiveCount(groupe) {
    if (groupe.groups) {
        return props.group.groups.map(recursiveCount).reduce((a, b) => a + b, 0)
    }
    else {
        return groupe.images.length
    }
}

const imageSum = computed(() => {
    if (!hasImages.value && !hasSubgroups.value) {
        return 0
    }
    return recursiveCount(props.group)

})
</script>

<template>
    <ExpandOption :small="props.small" :left-align="true">
        <template #name>{{ props.group.name }} ({{ imageSum }})<i class="h5 ms-2 bi bi-share"></i></template>
        <template #content>
            <div v-if="hasImages">
                <div class="row ms-3 images-group">
                    <div class="image-card" v-for="image in images">
                        <div class="image-container">
                            <img :src="image.url"/>
                        </div>
                        <div class="image-info" v-if="image.info">
                            Une prop
                        </div>
                    </div>
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

<style scoped="true">
.images-group {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  grid-gap: 20px;
}

.image-card {
  height: 100%;
  max-height: 300px;
  border: 1px solid #ccc;
  padding-left: 0;
  padding-right: 0;
}

.image-card img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-container{
    height: 100%;
}
</style>