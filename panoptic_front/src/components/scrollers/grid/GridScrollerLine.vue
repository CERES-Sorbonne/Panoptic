<script setup lang="ts">
import { GroupData, Property, ScrollerLine } from '@/data/models';
import { nextTick, onMounted, ref, watch } from 'vue';
import GroupLine from './GroupLine.vue';
import RowLine from './RowLine.vue';
import { GroupIterator, ImageIterator } from '@/utils/groups';


const props = defineProps({
    item: Object as () => ScrollerLine,
    width: Number,
    properties: Array<Property>,
    showImages: Boolean,
    selectedImages: Set<Number>,
    data: Object as () => GroupData
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
            <GroupLine :prop-values="item.data.propertyValues" :item="item" :width="props.width" :data="props.data"
                @close:group="e => emits('close:group', e)" @open:group="e => emits('open:group', e)" @toggle:group="emits('toggle:group', new GroupIterator(props.data, item.data.order))"/>
        </div>
        <div v-if="item.type == 'image'">
            <RowLine :item="item" :properties="props.properties" :show-image="props.showImages"
                @resizeHeight="h => emits('resizeHeight', h)" :selected="props.selectedImages.has(item.data.id)"
                @toggle:image="e => emits('toggle:image', new ImageIterator(props.data, props.data.index[e.groupId].order, e.imageIndex))" />
        </div>
    </template>
</template>

<style scoped>
.container {
    margin: 0;
    padding: 0;
}
</style>