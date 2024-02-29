<script setup lang="ts">
import GridScroller from '@/components/scrollers/grid/GridScroller.vue';
import { GroupManager } from '@/core/GroupManager';
import { Image, PropertyID, PropertyMode } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { computed, onMounted } from 'vue';

const store = useProjectStore()

const props = defineProps<{
    image: Image
    width: number
    height: number
    groupManager: GroupManager
}>()

const properties = computed(() => {
    const res = [store.data.properties[PropertyID.id]]
    res.push(...store.propertyList.filter(p => p.mode == PropertyMode.id))
    return res
})

onMounted(() => {
    props.groupManager.clear()
    props.groupManager.setSha1Mode(false)
    const images = store.data.sha1Index[props.image.sha1]
    props.groupManager.group(images, undefined, true)
})
</script>

<template>
    <div v-if="props.groupManager.hasResult()" class="m-0 p-0" style="overflow-x: scroll; overflow-y: hidden;" :style="{ width: props.width + 'px' }">
        <GridScroller :show-images="false" :manager="props.groupManager" :height="props.height" :width="props.width -15"
            :selected-properties="properties" />
    </div>
</template>