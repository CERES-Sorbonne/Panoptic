<script setup lang="ts">
import GridScroller from '@/components/scrollers/grid/GridScroller.vue';
import InstanceData from '@/components/data/InstanceData.vue';
import { GroupManager } from '@/core/GroupManager';
import { useDataStore } from '@/data/dataStore';
import { useColumnStore } from '@/data/columnStore';
import { InstanceEntry } from '@/data/instanceStore';
import { PropertyID, PropertyMode } from '@/data/models';
import { useTabStore } from '@/data/tabStore';
import { computed, onMounted, watch } from 'vue';

const data = useDataStore()
const col = useColumnStore()
const tabStore = useTabStore()

const props = defineProps<{
    image: InstanceEntry
    width: number
    height: number
}>()

// Own GroupManager — not shared with Similarity to avoid async race conditions
// when both views write to the same manager (sha1Mode, setAsRoot, group).
const manager = new GroupManager()

const properties = computed(() => {
    const idProp = data.getProperty('id')
    const rest = data.propertyList.filter(p => p.mode == PropertyMode.id && p.id != PropertyID.id)
    return idProp ? [idProp, ...rest] : rest
})

const allInstanceIds = computed(() => {
    const sha1 = props.image.sha1
    return sha1 ? col.getInstancesBySha1(sha1) : []
})

const propIds = computed(() => properties.value.map(p => p.id))

function update() {
    manager.clear()
    const sha1 = props.image.sha1
    const ids = sha1 ? col.getInstancesBySha1(sha1) : []
    const slots = ids.map(id => col.slotMap.get(id)).filter(s => s !== undefined) as number[]
    manager.group(new Int32Array(slots), true)
}

onMounted(update)
watch(() => props.image, update)
</script>

<template>
    <InstanceData :instance-ids="allInstanceIds" :prop-ids="propIds">
        <div class="m-0 p-0" style="overflow-x: scroll; overflow-y: hidden;"
            :style="{ width: props.width + 'px', height: props.height + 'px' }">
            <GridScroller :tab="tabStore.getMainTab()" :show-images="false" :manager="manager" :height="props.height" :width="props.width - 15"
                :selected-properties="properties" />
        </div>
    </InstanceData>
</template>