<script setup lang="ts">
import { Instance, ModalId, Tag } from '@/data/models';
import { computed, getCurrentInstance, onUnmounted, ref, watch } from 'vue'
import { useElementSize } from '@vueuse/core';
import ImageScroller from '@/components/scrollers/image/ImageScroller.vue';
import { useColumnStore } from '@/data/stores/columnStore';
import { useDataStore } from '@/data/stores/dataStore';
import EditableTag from '../tags/EditableTag.vue';
import { useInstanceStore } from '@/data/stores/instanceStore';
import { usePanopticStore } from '@/data/stores/panopticStore';

const instanceStore = useInstanceStore()
const panoptic = usePanopticStore()
const columnStore = useColumnStore()
const data = useDataStore()
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

// The flat list the scroller renders, built like the ImageModal's Similarity panel does.
const instances = computed<Instance[]>(() => {
    const sha1s = columnStore.sha1s()
    const list: Instance[] = []
    for (const id of instanceIds.value) {
        const slot = columnStore.slotMap.get(id)
        if (slot === undefined) continue
        list.push({ id, imageUrl: data.baseImgUrl + 'by_size/' + sha1s[slot] })
    }
    return list
})

const box = ref<HTMLElement | null>(null)
const { width, height } = useElementSize(box)

function openImage(instance: Instance) {
    const slot = columnStore.slotMap.get(instance.id)
    if (slot === undefined) return
    panoptic.showModal(ModalId.IMAGE, { slot })
}

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
        <div ref="box" class="flex-grow-1 overflow-hidden ms-2">
            <ImageScroller input-key="tag-images" :image-size="100" :height="height" :width="width"
                :instances="instances" :properties="[]" :no-drag="true" @open="openImage" />
        </div>
    </div>
</template>

<style scoped></style>