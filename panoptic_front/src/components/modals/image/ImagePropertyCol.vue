<script setup lang="ts">
import Zoomable from '@/components/Zoomable.vue';
import CenteredImage from '@/components/images/CenteredImage.vue';
import PropertyInputTable from '@/components/inputs/PropertyInputTable.vue';
import { GroupManager, ImageIterator } from '@/core/GroupManager';
import { deletedID, useDataStore } from '@/data/dataStore';
import { PropertyMode } from '@/data/models';
import { Ref, computed, inject, reactive, ref } from 'vue';

const data = useDataStore()

const props = defineProps<{
    image: ImageIterator
    width: number
    imageHeight: number
    visibleProperties: { [id: number]: boolean }
    groupManager: GroupManager
}>()

const emits = defineEmits<{
    paint: [e: { instanceId: number, propertyId: number }]
    hover
    hoverEnd
}>()

const mode = ref(0)
const img = new Image()
const nextImage: () => void = inject('nextImage')
const prevImage: () => void = inject('prevImage')
const showHistory: Ref<boolean> = inject('showHistory')

const closed = reactive({})



const properties = computed(() => {
    const res = []
    if (mode.value == 0) {
        res.push(...data.propertyList.filter(p => p.mode == PropertyMode.sha1 && !p.computed))
    }
    if (mode.value == 1) {
        res.push(...data.propertyList.filter(p => p.mode == PropertyMode.id && !p.computed))
    }
    if (mode.value == 2) {
        res.push(...data.propertyList.filter(p => p.computed))
    }
    return res.filter(p => p.id != deletedID)
})

const imageProperties = computed(() => data.propertyList.filter(p => p.mode == PropertyMode.sha1 && !p.computed && p.id != deletedID))
const instanceProperties = computed(() => data.propertyList.filter(p => p.mode == PropertyMode.id && !p.computed && p.id != deletedID))
const metaProperties = computed(() => data.propertyList.filter(p => p.id < 0 && p.id != deletedID))

function setMode(value) {
    mode.value = value
}

function toggleClosed(index: number) {
    if (closed[index]) {
        delete closed[index]
        return
    }
    closed[index] = true
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
        <div style="overflow-y: auto;">
            <div class="option" @click="toggleClosed(0)">
                <span>
                    <i v-if="closed[0]" class="bi bi-caret-right-fill" />
                    <i v-else class="bi bi-caret-down-fill"></i>
                </span>
                {{$t('common.properties.image')}}
            </div>
            <PropertyInputTable v-if="!closed[0]" :image="props.image.image" :properties="imageProperties"
                :visible-properties="visibleProperties" @paint="e => emits('paint', e)" @hover="emits('hover')"
                @hoverEnd="emits('hoverEnd')" />
            <div class="option" @click="toggleClosed(1)">
                <span>
                    <i v-if="closed[1]" class="bi bi-caret-right-fill" />
                    <i v-else class="bi bi-caret-down-fill"></i>
                </span>
                {{$t('common.properties.instance')}}
            </div>
            <PropertyInputTable v-if="!closed[1]" :image="props.image.image" :properties="instanceProperties"
                :visible-properties="visibleProperties" @paint="e => emits('paint', e)" @hover="emits('hover')"
                @hoverEnd="emits('hoverEnd')" />
            <div class="option" @click="toggleClosed(2)">
                <span>
                    <i v-if="closed[2]" class="bi bi-caret-right-fill" />
                    <i v-else class="bi bi-caret-down-fill"></i>
                </span>
                {{$t('common.properties.panoptic')}}</div>
            <PropertyInputTable v-if="!closed[2]" :image="props.image.image" :properties="metaProperties"
                :visible-properties="visibleProperties" @paint="e => emits('paint', e)" @hover="emits('hover')"
                @hoverEnd="emits('hoverEnd')" />
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
    font-size: 14px;
    line-height: 26px;
    background-color: var(--tab-grey);
    border-bottom: 1px solid var(--border-color);
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