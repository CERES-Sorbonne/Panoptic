<script setup lang="ts">
import CenteredImage from '@/components/images/CenteredImage.vue';
import PropertyInputTable from '@/components/inputs/PropertyInputTable.vue';
import { Image, PropertyMode } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { computed, ref } from 'vue';
const store = useProjectStore()
const props = defineProps<{
    image: Image
    width: number
    imageHeight: number
}>()

const showImageProps = ref(true)
const showInstanceProps = ref(true)

const properties = computed(() => {
    const res = []
    if(showImageProps.value) {
        res.push(...store.propertyList.filter(p => p.mode == PropertyMode.sha1))
    }
    if(showInstanceProps.value) {
        res.push(...store.propertyList.filter(p => p.mode == PropertyMode.id))
    }
    return res
})

</script>

<template>
    <div class="main2 bg-white h-100 d-flex flex-column " :style="{ width: props.width + 'px' }">
        <div class="image-container">
            <CenteredImage :image="image" :height="props.imageHeight" :width="props.width" />
        </div>
        <div class="custom-hr"></div>
        <div class="show-option"><input type="checkbox" v-model="showImageProps" /> <b>Propriétés d'image</b></div>
        <div class="show-option"><input type="checkbox" v-model="showInstanceProps" /> <b>Propriétés d'instance</b></div>
        <div class="flex-grow-1 overflow-scroll">
            <PropertyInputTable :image="props.image" :properties="properties"/>
        </div>
    </div>
</template>

<style scoped>

.main2 {
    border-right: 1px solid var(--border-color);
}

.show-option {
    padding: 5px 6px;
    border-bottom: 1px solid var(--border-color);
}

</style>