<script setup lang="ts">
import Zoomable from '@/components/Zoomable.vue';
import CenteredImage from '@/components/images/CenteredImage.vue';
import PropertyInputTable from '@/components/inputs/PropertyInputTable.vue';
import { ImageIterator } from '@/core/GroupManager';
import { Image as ImageType, ModalId, Property, PropertyMode, PropertyRef } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { useProjectStore } from '@/data/projectStore';
import { Ref, computed, inject, reactive, ref } from 'vue';
const panoptic = usePanopticStore()
const store = useProjectStore()
const props = defineProps<{
    image: ImageIterator
    width: number
    imageHeight: number
    visibleProperties: { [id: number]: boolean }
}>()

const emits = defineEmits<{
    paint: [e: PropertyRef]
}>()

const mode = ref(0)
const img = new Image()
const nextImage: () => void = inject('nextImage')
const prevImage: () => void = inject('prevImage')
const showHistory: Ref<boolean> = inject('showHistory')


const properties = computed(() => {
    const res = []
    if (mode.value == 0) {
        res.push(...store.propertyList.filter(p => p.mode == PropertyMode.sha1 && !p.computed))
    }
    if (mode.value == 1) {
        res.push(...store.propertyList.filter(p => p.mode == PropertyMode.id && !p.computed))
    }
    if (mode.value == 2) {
        res.push(...store.propertyList.filter(p => p.computed))
    }
    return res
})

function setMode(value) {
    mode.value = value
}




</script>

<template>
    <div class="main2 bg-white h-100 d-flex flex-column " :style="{ width: props.width + 'px' }">
        <div class="image-container position-relative">
            <Zoomable :image="props.image.image">
                <CenteredImage :image="props.image.image" :height="props.imageHeight" :width="props.width - 1" />
                <div class="image-nav d-flex" v-if="!showHistory && props.image.nextImages">
                    <div class="arrow" @click="prevImage"><i class="bi bi-arrow-left"></i></div>
                    <div class="flex-grow-1"></div>
                    <div class="arrow" @click="nextImage"><i class="bi bi-arrow-right"></i></div>
                </div>
            </Zoomable>
        </div>
        <div class="custom-hr"></div>
        <div class="d-flex text-center">
            <div class="option flex-grow-1" :class="mode == 0 ? 'selected' : ''" @click="setMode(0)">Propriétés d'image
            </div>
            <div class="sep"></div>
            <div class="option flex-grow-1" :class="mode == 1 ? 'selected' : ''" @click="setMode(1)">Propriétés d'instance
            </div>
            <div class="sep"></div>
            <div class="option flex-grow-1" :class="mode == 2 ? 'selected' : ''" @click="setMode(2)">Metadonées</div>
        </div>
        <div class="custom-hr"></div>
        <div class="flex-grow-1 overflow-scroll">
            <PropertyInputTable :image="props.image.image" :properties="properties" :visible-properties="visibleProperties"
                @paint="e => emits('paint', e)" />
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

.image-nav {
    position: absolute;
    font-size: 30px;
    top: 10px;
    left: 0;
    right: 0;
    padding: 0px 10px;
}

.arrow {
    padding: 5px;
    cursor: pointer;
    line-height: 10px;
    border-radius: 50%;
}

.arrow:hover {
    background-color: var(--tab-grey);
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
}</style>