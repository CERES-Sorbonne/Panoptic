<script setup lang="ts">
import { computed } from 'vue';
import { type Property } from '@/data/models'
import { PileRowLine, type GroupLine, type RowLine, type ScrollerLine } from '@/components/scrollers/types'

import GroupLineVue from './GroupLine.vue';
import RowLineVue from './RowLine.vue';
import { SelectedImages } from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { TabManager } from '@/core/TabManager';
import { useColumnStore } from '@/data/stores/columnStore';


const props = defineProps<{
    tab: TabManager,
    imageSize: number,
    manager: GroupInspector,
    item: ScrollerLine,
    width: number,
    missingWidth: number,
    properties: Property[],
    showImages: boolean,
    rowHeight: number,
}>()

const emits = defineEmits({
    'close:group': String,
    'open:group': String,
    'toggle:image': Object,
    'toggle:group': Object
})

const columnStore = useColumnStore()

const selected = computed(() => {
    columnStore.selectionVersion  // reactive dep on global selection (step 2)
    if (props.item.type == 'image') {
        return columnStore.isSelectedId((props.item as RowLine).data.id)
    } else if (props.item.type == 'pile') {
        return columnStore.isSelected((props.item as PileRowLine).data.slots[0])
    }
})

// A recycled view keeps its row components and only gets a new `item`: everything below is
// derived from props, and DBInput remounts its cell editor when the instance changes. (This
// used to unmount and remount the whole row on every item change, which made scrolling and
// opening groups rebuild every visible cell.)

</script>

<template>
    <div v-if="item.type == 'group'">
        <GroupLineVue :item="(item as GroupLine)" :manager="props.manager" :width="props.width"
            @close:group="e => emits('close:group', e)"
            @open:group="e => emits('open:group', e)" @toggle:group="e => emits('toggle:group', e)" />
    </div>
    <div v-if="item.type == 'image'">
        <!-- <div class="border-top position-absolute border-warning" style="width: 100%;"></div> -->
        <RowLineVue :tab="props.tab" :image-size="props.imageSize" :manager="props.manager" :item="(item as RowLine)" :properties="props.properties" :show-image="props.showImages"
            :missing-width="props.missingWidth" :row-height="props.rowHeight"
            @toggle:image="e => emits('toggle:image', e)" :selected="selected" />
    </div>
    <div v-if="item.type == 'pile'">
        <RowLineVue :tab="props.tab" :image-size="props.imageSize" :manager="props.manager" :item="(item as PileRowLine)" :properties="props.properties" :show-image="props.showImages"
            :missing-width="props.missingWidth" :row-height="props.rowHeight" :selected="selected"
            @toggle:image="e => emits('toggle:image', { groupId: (item as PileRowLine).data.groupId, imageIndex: (item as PileRowLine).data.pileIndex })" />
    </div>
    <div v-if="item.type == 'filler'" style="height: 1000px;">

    </div>
</template>

<style scoped>
</style>