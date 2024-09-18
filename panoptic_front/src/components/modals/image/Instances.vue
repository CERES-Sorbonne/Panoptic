<script setup lang="ts">
import GridScroller from '@/components/scrollers/grid/GridScroller.vue';
import { GroupManager } from '@/core/GroupManager';
import { useDataStore } from '@/data/dataStore';
import { Instance, PropertyID, PropertyMode } from '@/data/models';
import { computed, onMounted, watch } from 'vue';

const data = useDataStore()

const props = defineProps<{
    image: Instance
    width: number
    height: number
    groupManager: GroupManager
}>()

const properties = computed(() => {
    const res = [data.properties[PropertyID.id]]
    res.push(...data.propertyList.filter(p => p.mode == PropertyMode.id && p.id != PropertyID.id))
    return res
})

function update() {
    props.groupManager.clear()
    props.groupManager.setSha1Mode(false)
    const images = data.sha1Index[props.image.sha1]
    props.groupManager.group(images, undefined, true)
}

onMounted(update)
watch(() => props.image, update)
</script>

<template>
    <div v-if="props.groupManager.hasResult()" class="m-0 p-0" style="overflow-x: scroll; overflow-y: hidden;"
        :style="{ width: props.width + 'px', height: props.height + 'px' }">
        <GridScroller :show-images="false" :manager="props.groupManager" :height="props.height" :width="props.width - 15"
            :selected-properties="properties" />
    </div>
</template>