<script setup lang="ts">
import { Ref, computed, nextTick, onMounted, ref, watch } from 'vue';
import { PileRowLine, type GroupLine, type Property, type RowLine, type ScrollerLine } from '@/data/models'

import GroupLineVue from './GroupLine.vue';
import RowLineVue from './RowLine.vue';
import { SelectedImages } from '@/core/GroupManager';
import { TabManager } from '@/core/TabManager';


const props = defineProps<{
    tab: TabManager,
    item: ScrollerLine,
    width: number,
    missingWidth: number,
    properties: Property[],
    showImages: boolean,
    selectedImages: Ref<SelectedImages>
}>()

const emits = defineEmits({
    'resizeHeight': Number,
    'close:group': String,
    'open:group': String,
    'toggle:image': Object,
    'toggle:group': Object
})

const loaded = ref(true)

const selected = computed(() => {
    if (props.item.type == 'image') {
        return props.selectedImages.value[props.item.data.id]
    } else if( props.item.type = 'pile') {
        return props.selectedImages.value[props.item.data.images[0].id]
    }
})

function reload() {
    loaded.value = false
    nextTick(() => nextTick(() => loaded.value = true))
}

// onMounted(reload)
watch(() => props.item.id, reload)

</script>

<template>
    <template v-if="loaded" class="container">
        <div v-if="item.type == 'group'">
            <GroupLineVue :prop-values="item.data.propertyValues" :item="(item as GroupLine)" :width="props.width"
                :selectedImages="props.selectedImages" @close:group="e => emits('close:group', e)"
                @open:group="e => emits('open:group', e)" @toggle:group="e => emits('toggle:group', e)" />
        </div>
        <div v-if="item.type == 'image'">
            <!-- <div class="border-top position-absolute border-warning" style="width: 100%;"></div> -->
            <RowLineVue :tab="props.tab" :item="(item as RowLine)" :properties="props.properties" :show-image="props.showImages"
                :missing-width="props.missingWidth" @resizeHeight="h => emits('resizeHeight', h)"
                @toggle:image="e => emits('toggle:image', e)" :selected="selected" />
        </div>
        <div v-if="item.type == 'pile'">
            <RowLineVue :tab="props.tab" :item="(item as PileRowLine)" :properties="props.properties" :show-image="props.showImages"
                :missing-width="props.missingWidth" @resizeHeight="h => emits('resizeHeight', h)" :selected="selected"
                @toggle:image="e => emits('toggle:image', { groupId: item.data.parent.id, imageIndex: item.data.parentIdx })" />
        </div>
        <div v-if="item.type == 'filler'" style="height: 1000px;">

        </div>
    </template>
</template>

<style scoped>
.container {
    margin: 0;
    padding: 0;
}
</style>