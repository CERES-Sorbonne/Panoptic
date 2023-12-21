<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
import { GroupLine, Property, ScrollerLine } from '@/data/models'

import GroupLineVue from './GroupLine.vue';
import RowLine from './RowLine.vue';
import { SelectedImages } from '@/core/GroupManager';


const props = defineProps({
    item: Object as () => ScrollerLine,
    width: Number,
    missingWidth: Number,
    properties: Array<Property>,
    showImages: Boolean,
    selectedImages: Object as () => SelectedImages,
    data: Object
})
const emits = defineEmits({
    'resizeHeight': Number,
    'close:group': String,
    'open:group': String,
    'toggle:image': Object,
    'toggle:group': Object
})

const loaded = ref(true)

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
                :data="props.data" @close:group="e => emits('close:group', e)" @open:group="e => emits('open:group', e)"
                @toggle:group="e => emits('toggle:group', e)" />
        </div>
        <div v-if="item.type == 'image'">
            <RowLine :item="item" :properties="props.properties" :show-image="props.showImages"
                :missing-width="props.missingWidth" @resizeHeight="h => emits('resizeHeight', h)"
                @toggle:image="e => emits('toggle:image', e)" :selected="props.selectedImages[item.data.id]" />
        </div>
        <div v-if="item.type == 'pile'">
            <RowLine :item="item" :properties="props.properties" :show-image="props.showImages"
                :missing-width="props.missingWidth" @resizeHeight="h => emits('resizeHeight', h)"
                :selected="props.selectedImages[item.data.images[0].id]"
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