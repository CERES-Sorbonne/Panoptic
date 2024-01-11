<script setup lang="ts">
import CenteredImage from '@/components/images/CenteredImage.vue';
import PropertyInputTable from '@/components/inputs/PropertyInputTable.vue';
import { Image, Property, PropertyMode, PropertyRef } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { computed, reactive, ref } from 'vue';
const store = useProjectStore()
const props = defineProps<{
    image: Image
    width: number
    imageHeight: number
    visibleProperties: {[id: number]: boolean}
}>()

const emits = defineEmits<{
    paint: [e: PropertyRef]
}>()

const mode = ref(0)

const properties = computed(() => {
    const res = []
    if (mode.value == 0) {
        res.push(...store.propertyList.filter(p => p.mode == PropertyMode.sha1))
    }
    if (mode.value == 1) {
        res.push(...store.propertyList.filter(p => p.mode == PropertyMode.id))
    }
    if (mode.value == 2) {
        res.push(...store.propertyList.filter(p => p.mode == PropertyMode.computed))
    }
    return res
})

function setMode(value) {
    mode.value = value
}

</script>

<template>
    <div class="main2 bg-white h-100 d-flex flex-column " :style="{ width: props.width + 'px' }">
        <div class="image-container">
            <CenteredImage :image="image" :height="props.imageHeight" :width="props.width" />
        </div>
        <div class="custom-hr"></div>
        <div class="d-flex text-center">
            <div class="option flex-grow-1" :class="mode == 0 ? 'selected' : ''" @click="setMode(0)">Propriétés d'image</div>
            <div class="sep"></div>
            <div class="option flex-grow-1" :class="mode == 1 ? 'selected' : ''" @click="setMode(1)">Propriétés d'instance</div>
            <div class="sep"></div>
            <div class="option flex-grow-1" :class="mode == 2 ? 'selected' : ''" @click="setMode(2)">Metadonées</div>
        </div>
        <div class="custom-hr"></div>
        <!-- <div class="show-option"><input type="checkbox" v-model="showImageProps" /> <b>Propriétés d'image</b></div>
        <div class="show-option"><input type="checkbox" v-model="showInstanceProps" /> <b>Propriétés d'instance</b></div>
        <div class="show-option"><input type="checkbox" v-model="showMetaData" /> <b>Metadonées</b></div> -->
        <div class="flex-grow-1 overflow-scroll">
            <PropertyInputTable :image="props.image" :properties="properties" :visible-properties="visibleProperties" @paint="e => emits('paint', e)" />
        </div>
    </div>
</template>

<style scoped>
.main2 {
    border-right: 1px solid var(--border-color);
}

.sep {
    border-left: 1px solid var(--border-color);
}

.option {
    font-size: 13px;
    line-height: 26px;
    background-color: var(--tab-grey);
    /* border-bottom: 1px solid var(--border-color); */
    cursor: pointer;
}

.selected {
    /* border-bottom: 1px solid white; */
    background-color: white;
}

.show-option {
    padding: 5px 6px;
    border-bottom: 1px solid var(--border-color);
    background-color: var(--grey);
}
</style>