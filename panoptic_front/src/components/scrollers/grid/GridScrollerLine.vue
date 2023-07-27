<script setup lang="ts">
import { Property, ScrollerLine } from '@/data/models';
import { nextTick, onMounted, ref, watch } from 'vue';
import GroupLine from './GroupLine.vue';
import RowLine from './RowLine.vue';


const props = defineProps({
    item: Object as () => ScrollerLine,
    width: Number,
    properties: Array<Property>,
    showImages: Boolean
})
const emits = defineEmits({
    'resizeHeight': Number
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
    <template v-if="loaded">
        <div v-if="item.type == 'group'">
            <GroupLine :prop-values="item.data.propertyValues" :item="item" :width="props.width" />
        </div>
        <div v-if="item.type == 'image'">
            <RowLine :item="item" :properties="props.properties" :show-image="props.showImages"
                @resizeHeight="h => emits('resizeHeight', h)" />
        </div>
    </template>
</template>