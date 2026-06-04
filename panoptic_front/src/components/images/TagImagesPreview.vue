<script setup lang="ts">
import { Instance, Tag } from '@/data/models';
import { computed, getCurrentInstance, onUnmounted, watch } from 'vue'
import ImagePreview from '../preview/ImagePreview.vue';
import EditableTag from '../tags/EditableTag.vue';
import { useInstanceStore } from '@/data/instanceStore';
import { usePanopticStore } from '@/data/panopticStore';

const instanceStore = useInstanceStore()
const panoptic = usePanopticStore()
const uid = String(getCurrentInstance()!.uid)

const props = defineProps<{
    tags: Tag[]
    tagToInstance: { [tId: number]: Instance[] }
}>()

const emits = defineEmits(['unselect', 'merge'])

const instanceIds = computed(() => {
    const instanceSet = new Set<number>()
    for (const tag of props.tags) {
        props.tagToInstance[tag.id]?.forEach(i => instanceSet.add(i.id))
    }
    return Array.from(instanceSet)
})

watch(instanceIds, (ids) => {
    const projectId = panoptic.connectionState?.connectedProject ?? ''
    instanceStore.register(uid, ids, [], projectId)
}, { immediate: true })

onUnmounted(() => instanceStore.unregister(uid))

function mergeSelected() {
    emits('merge')
}

</script>

<template>
    <div class="h-100 w-100 d-flex flex-column overflow-hidden">
        <div class="flex-shrink-0" style="max-height: 222px; overflow-y: auto; overflow-x: auto;">
            <EditableTag v-for="tag in props.tags" :tag="tag" @unselect="e => emits('unselect', e)" />
        </div>
        <div v-if="props.tags.length > 1" style="height: 37px; border-bottom: 1px solid var(--border-color);" class="flex-shrink-0 text-center bb"
        @click="mergeSelected">
            <!-- <div style="margin-top: 6px;">
                <span class="bbb">Fusion</span>
            </div> -->
            <div style="margin-top: 4px;">Merge Tags</div>
        </div>

        <div class="flex-shrink-0" style="height: 4px;"></div>
        <ImagePreview :instance-ids="instanceIds" />
    </div>
</template>

<style scoped></style>