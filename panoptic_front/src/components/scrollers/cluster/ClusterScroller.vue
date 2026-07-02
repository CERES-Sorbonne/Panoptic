<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed, Ref, shallowRef, provide } from 'vue';
import ClusterLineVue from './ClusterLine.vue';
import { GroupManager, Group } from '@/core/GroupManager';
import { keyState } from '@/data/keyState';
import { Property, ClusterLine, ModalId } from '@/data/models';
import { RecycleScroller } from 'vue-virtual-scroller';
import { usePanopticStore } from '@/data/panopticStore';
import { useColumnStore } from '@/data/columnStore';
import InstanceData from '@/components/data/InstanceData.vue';

const panoptic = usePanopticStore()
const columnStore = useColumnStore()

const props = defineProps<{
    imageSize: number,
    height: number,
    width: number,
    groupManager: GroupManager,
    properties: Property[],
    hideIfModal?: boolean,
    inputKey: string
}>()

const emit = defineEmits(['reco'])

provide('inputKey', props.inputKey)
provide('selectNamespace', computed(() => props.groupManager?.selectionNamespace ?? 'global'))

const clusterLines = shallowRef([]) as Ref<ClusterLine[]>

const hoverGroupBorder = ref(-1)

const scroller = ref(null)
const MARGIN_STEP = 20

const clusterLineSize = computed(() => props.imageSize + 40)

const maxPerLine = computed(() => Math.ceil(props.width / props.imageSize * 1.5))

const hideFromModal = computed(() => props.hideIfModal && (panoptic.openModalId == ModalId.IMAGE || panoptic.openModalId == ModalId.TAG))

provide('hideImg', hideFromModal)

const windowStart = ref(0)
const windowEnd   = ref(0)

function onScrollerUpdate(startIndex: number, endIndex: number) {
    windowStart.value = startIndex
    windowEnd.value   = endIndex
}

const windowIds = computed(() => {
    const ids: number[] = []
    const lines = clusterLines.value
    if (!lines.length) return ids

    let start = Math.max(0, Math.min(windowStart.value, lines.length - 1))
    let end   = Math.max(0, Math.min(windowEnd.value, lines.length - 1))

    let preCount = 0
    while (start > 0 && preCount < 5) {
        start--
        if (lines[start].type === 'cluster') preCount++
    }

    let postCount = 0
    while (end < lines.length - 1 && postCount < 5) {
        end++
        if (lines[end].type === 'cluster') postCount++
    }

    for (let i = start; i <= end; i++) {
        const line = lines[i]
        if (line.type === 'cluster') {
            for (const entry of (line as ClusterLine).data) {
                const instanceId = columnStore.instanceIds()[entry.slot]
                if (instanceId !== undefined && !isNaN(instanceId)) {
                    ids.push(instanceId)
                }
            }
        }
    }
    return ids
})

const windowPropIds = computed(() => props.properties?.map(p => p.id) ?? [])

defineExpose({
    computeLines,
    clear
})

function clear() {
    clusterLines.value = []
}

function sameLine(a: ClusterLine, b: ClusterLine): boolean {
    if (!a || a.type !== b.type || a.size !== b.size) return false
    if (a.id !== b.id) return false
    const ad = a.data, bd = b.data
    if (ad.length !== bd.length) return false
    for (let i = 0; i < ad.length; i++) {
        if (ad[i].slot !== bd[i].slot || ad[i].group.id !== bd[i].group.id) return false
    }
    return true
}

function reconcileLines(prev: ClusterLine[], next: ClusterLine[]): ClusterLine[] {
    if (!prev.length) return next
    const byId = new Map<any, ClusterLine>()
    for (const l of prev) byId.set(l.id, l)
    for (let i = 0; i < next.length; i++) {
        const old = byId.get(next[i].id)
        if (old && sameLine(old, next[i])) next[i] = old
    }
    return next
}

type ClusterEntry = { group: Group, slot: number }

let _computingLines = false
function computeLines() {
    if (_computingLines) return
    _computingLines = true
    try {
        const root = props.groupManager.result.root
        if (!root) {
            clusterLines.value = []
            return
        }
        const candidates: ClusterEntry[] = []
        for (const child of root.children) {
            if (child.slots && child.slots.length > 0) {
                candidates.push({ group: child, slot: child.slots[0] })
            }
        }
        if (candidates.length === 0 && root.slots && root.slots.length > 0) {
            candidates.push({ group: root, slot: root.slots[0] })
        }

        const lines: ClusterLine[] = []
        const itemWidth = props.imageSize + 12
        const depth = root.depth + 1
        const lineWidth = props.width - (depth * MARGIN_STEP)
        let newLine: ClusterEntry[] = []
        let actualWidth = 0
        let groupLineIndex = 0

        for (const entry of candidates) {
            if (actualWidth + itemWidth < lineWidth) {
                newLine.push(entry)
                actualWidth += itemWidth
                continue
            }
            if (newLine.length === 0) {
                newLine.push(entry)
            }
            lines.push({
                id: root.id + '|cli-' + groupLineIndex++,
                type: 'cluster',
                data: newLine,
                groupId: root.id,
                depth: root.depth + 1,
                size: clusterLineSize.value
            })
            newLine = [entry]
            actualWidth = itemWidth
        }

        if (newLine.length > 0) {
            lines.push({
                id: root.id + '|cli-' + groupLineIndex++,
                type: 'cluster',
                data: newLine,
                groupId: root.id,
                depth: root.depth + 1,
                size: clusterLineSize.value
            })
        }

        clusterLines.value = reconcileLines(clusterLines.value, lines)
    } finally {
        _computingLines = false
    }
}

function scrollTo(groupId) {
    const idx = clusterLines.value.findIndex(l => l.groupId === groupId)
    if (idx >= 0) {
        scroller.value.scrollToItem(idx)
        nextTick(() => scroller.value.updateVisibleItems(true))
    }
}

function updateHoverBorder(value) {
    hoverGroupBorder.value = value
}

function getParents(group: Group) {
    const ids: number[] = []
    const seen = new Set<number>()
    let current = group?.parent
    while (current != undefined && !seen.has(current.id)) {
        seen.add(current.id)
        ids.unshift(current.id)
        current = current.parent
    }
    return ids
}

function getClusterLineParents(item: ClusterLine) {
    if (!item.groupId) return []
    const parentGroup = props.groupManager.result.index[item.groupId]
    return parentGroup ? [...getParents(parentGroup), item.groupId] : [item.groupId]
}

function toggleClusterSelect(groupId: number) {
    const iterator = props.groupManager.getGroupIterator(groupId)
    if (iterator) props.groupManager.toggleGroupIterator(iterator, keyState.shift)
}

let _triggerHandle: ReturnType<typeof setTimeout> | undefined
function triggerUpdate() {
    clearTimeout(_triggerHandle)
    _triggerHandle = setTimeout(computeLines, 50)
}

onMounted(computeLines)

watch(() => props.imageSize, () => {
    nextTick(computeLines)
})

let resizeWidthHandler: ReturnType<typeof setTimeout> | undefined
watch(() => props.width, () => {
    clearTimeout(resizeWidthHandler)
    resizeWidthHandler = setTimeout(computeLines, 200)
})

watch(() => props.groupManager.version.value, triggerUpdate)
</script>

<template>
    <div v-if="clusterLines.length === 0" class="p-3 text-secondary">No clusters to display</div>
    <InstanceData v-else :instance-ids="windowIds" :prop-ids="windowPropIds">
    <RecycleScroller :items="clusterLines" key-field="id" ref="scroller" :style="'height: ' + props.height + 'px;'"
        :buffer="400" :min-item-size="0" :emitUpdate="true" @update="onScrollerUpdate" :page-mode="false" :prerender="0">
        <template v-slot="{ item, index, active }">
            <div v-if="item.type == 'cluster'">
                <ClusterLineVue :image-size="props.imageSize" :input-index="index * maxPerLine" :item="item"
                    :parent-ids="getClusterLineParents(item)"
                    :hover-border="hoverGroupBorder"
                    :manager="props.groupManager"
                    :properties="props.properties"
                    @hover="updateHoverBorder"
                    @unhover="hoverGroupBorder = -1"
                    @select-cluster="toggleClusterSelect"
                    @scroll="scrollTo"
                    @reco="emit('reco', $event)" />
            </div>
        </template>
    </RecycleScroller>
    </InstanceData>
</template>
