<script setup lang="ts">
import { ComputedRef, computed, inject, ref, watch } from 'vue'
import StampDropdown from '@/components/inputs/StampDropdown.vue'
import PropertyValue from '@/components/properties/PropertyValue.vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import { ClusterRequest, Group, GroupManager, GroupTree, GroupType } from '@/core/GroupManager'
import { GroupLine, ImagePropertyValue, InstancePropertyValue, Property, PropertyMode, PropertyType, Tag, buildTag } from '@/data/models'
import ActionButton from '@/components/actions/ActionButton.vue'
import { useDataStore } from '@/data/dataStore'
import { useColumnStore } from '@/data/columnStore' // <-- Imported columnStore
import { allChildrenSha1Groups } from '@/utils/utils'
import ActionButton2 from '@/components/actions/ActionButton2.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import WithToolTip from '../../tooltips/withToolTip.vue'
import { apiAllocateTags } from '@/data/apiProjectRoutes'

const data = useDataStore()
const columnStore = useColumnStore() // <-- Initialized column store
const selectNamespace = inject<ComputedRef<string>>('selectNamespace', computed(() => 'global'))

const props = defineProps<{
    item: GroupLine
    manager: GroupManager
    parentIds: number[];
    hoverBorder: number,
    data: GroupTree,
    hideOptions: boolean
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'group:close', 'group:open', 'group:update', 'select', 'reco'])

const hoverGroup = ref(false)

// The group tree is plain, non-reactive data: the manager's `version` ref is the only
// change signal. Every computed derived from the tree must read it, otherwise it caches
// its first value and refreshes only when some *other* reactive dep of this component
// happens to change (which is why e.g. the open/close-all button appeared late).
const version = computed(() => props.manager.version.value)

const group = computed(() => (version.value, props.item.data))

const slots = computed(() => (version.value, props.item.data.slots ?? []))

function getImages() {
    const ids = columnStore.instanceIds()
    const sha1s = columnStore.sha1s()
    return slots.value.map(slot => ({ id: ids[slot], imageUrl: data.baseImgUrl + 'by_size/' + sha1s[slot], sha1: sha1s[slot] }))
}

const subgroups = computed(() => (version.value, props.item.data.children ?? []))
const hasImages = computed(() => slots.value.length > 0)

const hasSubgroups = computed(() => {
    return subgroups.value.length > 0
})
const properties = computed(() => (version.value, props.item.data.meta.propertyValues.map(v => data.properties[v.propertyId])))
const propertyValues = computed(() => (version.value, props.item.data.meta.propertyValues))
const closed = computed(() => (version.value, props.item.data.view.closed))
const hasOpenChildren = computed(() => subgroups.value.some((c: Group) => !c.view.closed))

// Reactive via the namespace's selection tick, read inside isGroupSelected.
const selected = computed(() => props.manager.isGroupSelected(props.item.data))

const groupName = computed(() => {
    version.value
    if (props.item.data.type == GroupType.All) return 'All'
    if (props.item.data.type == GroupType.Cluster) return props.item.data.name ?? ('Cluster ' + props.item.data.parentIdx)
    return 'tmp name'
})

const isClusterGroup = computed(() => (version.value, props.item.data.subGroupType == GroupType.Cluster))

// Clustering this group. The button hands over the function + params and is done: the
// ClusterManager owns the run, so the clusters appear even if this line has been scrolled out
// of the virtualized list (i.e. unmounted) by the time the backend answers.
function cluster(req: ClusterRequest) {
    props.manager.cluster(props.item.data.id, req)
}

function clear() {
    props.manager.delCustomGroups(props.item.data.id, true)
}

// open/close mutate `view.closed` in place on the plain tree, so they must emit
// (bump `version`) — the scroller event alone rebuilds lines but leaves every
// tree-derived computed in this and every other line component stale.
function toggleClosed() {
    if (closed.value) {
        props.manager.toggleGroup(props.item.data.id, true)
        emits('group:open', props.item.id)
    }
    else {
        props.manager.toggleGroup(props.item.data.id, true)
        emits('group:close', props.item.id)
    }
}

function closeChildren() {
    const ids = subgroups.value.map((g: Group) => g.id)
    ids.forEach((id: number) => props.manager.closeGroup(id))
    props.manager.emitResult()
    emits('group:close', ids)
}

function openChildren() {
    const ids = subgroups.value.map((g: Group) => g.id)
    ids.forEach((id: number) => props.manager.openGroup(id))
    props.manager.emitResult()
    emits('group:open', ids)
}

const saving = ref(false)
async function saveHirachy(ignoreParents?: boolean) {
    if (saving.value) return
    saving.value = true

    const children = group.value.children
    const mode = allChildrenSha1Groups(group.value) ? PropertyMode.sha1 : PropertyMode.id

    // Count how many tags are needed before allocating
    const tagCount = countTags(children, ignoreParents)

    // Allocate real IDs for the property and all tags in parallel
    const property: Property = { id: -1, name: 'Clustering', type: PropertyType.multi_tags, mode: mode }
    const [realTagIds, realPropId] = await Promise.all([
        apiAllocateTags(tagCount),
        data.sendCommit({ properties: [property] }).then(res => res.properties[0].id),
    ])

    // Build tags directly with real IDs using an index into the allocated range
    let idxRef = { i: 0 }
    const nextId = () => realTagIds[idxRef.i++]
    const tagToImages: { [tagId: number]: any[] } = {}
    const tags = childrenToTags(children, nextId, undefined, tagToImages, realPropId, ignoreParents)

    const instanceValues: InstancePropertyValue[] = []
    const imageValues: ImagePropertyValue[] = []
    for (const tagId in tagToImages) {
        for (const img of tagToImages[tagId]) {
            if (mode == PropertyMode.id) {
                instanceValues.push({ propertyId: realPropId, instanceId: img.id, value: [Number(tagId)] })
            } else {
                imageValues.push({ propertyId: realPropId, sha1: data.getSysField(img.id, 'sha1'), value: [Number(tagId)] })
            }
        }
    }

    await data.sendCommit({ tags, instanceValues, imageValues })
    saving.value = false
}

function countTags(children: Group[], ignoreParents?: boolean): number {
    let count = 0
    for (const child of children) {
        const hasSubgroups = child.children.length > 0
        if (hasSubgroups) {
            if (!ignoreParents) count++ // parent tag
            count += countTags(child.children, ignoreParents)
        } else {
            count++
        }
    }
    return count
}

function childrenToTags(children: Group[], nextId: () => number, parentTag: Tag | undefined, tagToImages: { [tagId: number]: any[] }, propertyId: number, ignoreParents?: boolean) {
    const res: Tag[] = []
    const prefix = parentTag?.value ?? ('Clustering_' + children.length)
    const parentIds = parentTag && !ignoreParents ? [parentTag.id] : []

    for (let i = 0; i < children.length; i++) {
        const child = children[i]
        const hasSubgroups = child.children.length > 0

        if (hasSubgroups && ignoreParents) {
            // Skip intermediate parent tags — recurse directly without creating a tag for this level
            const subRes = childrenToTags(child.children, nextId, parentTag, tagToImages, propertyId, ignoreParents)
            res.push(...subRes)
        } else {
            const tag = buildTag(nextId(), propertyId, prefix + '.' + i, parentIds)
            res.push(tag)

            if (hasSubgroups) {
                const subRes = childrenToTags(child.children, nextId, tag, tagToImages, propertyId, ignoreParents)
                res.push(...subRes)
            } else {
                const childSlots = child.slots ?? []
                const ids = columnStore.instanceIds()
                tagToImages[tag.id] = childSlots.map(slot => ({ id: ids[slot] }))
            }
        }
    }
    return res
}

</script>

<template>
    <div class="d-flex flex-row group-line m-0 p-0 overflow-hidden"
        @mouseenter="hoverGroup = true" @mouseleave="hoverGroup = false">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2"
            @click="$emit('scroll', parentId)" @mouseenter="$emit('hover', parentId)" @mouseleave="$emit('unhover')">
            <div class="group-line-border" :class="props.hoverBorder == parentId ? 'active' : ''"> </div>
        </div>
        <div @click="toggleClosed" class="align-self-center me-2" style="cursor: pointer;">
            <i v-if="closed" class="bi bi-caret-right-fill" style="margin-left: 1px;"></i>
            <i v-else class="bi bi-caret-down-fill" style="margin-left: 1px;"></i>
        </div>
        <div class="me-1">
            <SelectCircle :small="true" :model-value="selected" @update:model-value="emits('select', group.id)" />
        </div>
        <div v-if="hasSubgroups && hasOpenChildren"
            class="text-secondary align-self-center bi bi-dash-square-dotted me-1" @click="closeChildren">
        </div>
        <div v-if="hasSubgroups && !hasOpenChildren"
            class="text-secondary align-self-center bi bi-plus-square-dotted me-1" @click="openChildren">
        </div>
        <div v-if="properties.length" :style="'font-size: ' + (Math.max(17 - (1 * props.item.depth), 10)) + 'px;'"
            class="align-self-center me-2">
            <template v-for="propValue in propertyValues">
                <PropertyValue :value="propValue" />
            </template>

        </div>
        <div v-else class="align-self-center me-2"><b>{{ groupName }}</b></div>
        <div v-if="group.type == GroupType.Cluster" style="padding-top: 2.5px;" class="me-2">
            <ClusterBadge v-if="group.score" :value="Math.round(group.score.value)" />
        </div>

        <div class="align-self-center me-2 text-secondary" style="font-size: 11px;">{{ slots.length }} Images
        </div>

        <div v-if="subgroups.length" class="align-self-center me-2 text-secondary" style="font-size: 11px;">{{
            subgroups.length }} {{ $t('main.view.groupes_nb') }}</div>

        <template v-if="!closed && !props.hideOptions">
            <template v-if="group.subGroupType == GroupType.Cluster">
                <div class="ms-1">
                    <WithToolTip message="btn.close-clusters">
                        <div class="sb opt-btn" @click="clear">
                            <i class="bi bi-x-lg" />
                        </div>
                    </WithToolTip>
                </div>
            </template>

            <!-- Options dropdown: always visible -->
            <div v-if="group.subGroupType != GroupType.Cluster" class="ms-1">
                <Dropdown :teleport="true">
                    <template #button>
                        <div class="sb opt-btn"><i class="bi bi-three-dots" /></div>
                    </template>
                    <template #popup="{ hide }">
                        <div class="opt-menu">
                            <StampDropdown v-if="!hasSubgroups" :images="getImages" :no-border="true">
                                <template #button>
                                    <div class="opt-row">
                                        <span class="opt-icon"><i class="bi bi-paint-bucket" /></span>
                                        <span class="opt-label">{{ $t('dropdown.stamp.paint_group') }}</span>
                                    </div>
                                </template>
                            </StampDropdown>

                            <ActionButton2 v-if="!hasSubgroups" action="group" :no-border="true" :defer="true"
                                :busy="props.manager.isClustering(group.id)" @submit="cluster">
                                <div class="opt-row">
                                    <span class="opt-icon"><i class="bi bi-intersect" /></span>
                                    <span class="opt-label">{{ $t('action.group') }}</span>
                                </div>
                            </ActionButton2>

                            <ActionButton2 action="execute" :no-border="true" :defer="true"
                                :busy="props.manager.isClustering(group.id)" @submit="cluster">
                                <div class="opt-row">
                                    <span class="opt-icon"><i class="bi bi-terminal" /></span>
                                    <span class="opt-label">{{ $t('action.execute') }}</span>
                                </div>
                            </ActionButton2>

                            <div v-if="!hasSubgroups" class="opt-row" @click="emits('reco', group.id); hide();">
                                <span class="opt-icon"><i class="bi bi-magic" /></span>
                                <span class="opt-label">{{ $t('main.menu.reco_tooltip') }}</span>
                            </div>

                            <template v-if="group.subGroupType == GroupType.Cluster">
                                <div class="opt-row" @click="saveHirachy(); hide();">
                                    <span class="opt-icon"><i class="bi bi-diagram-3" /></span>
                                    <span class="opt-label">{{ $t('btn.save-clusters') }}</span>
                                </div>
                                <div class="opt-row" @click="saveHirachy(true); hide();">
                                    <span class="opt-icon"><i class="bi bi-floppy2-fill" /></span>
                                    <span class="opt-label">{{ $t('btn.save-clusters') }}</span>
                                </div>
                            </template>
                        </div>
                    </template>
                </Dropdown>
            </div>

            <!-- Fast-access actions: visible only while hovering the group line.
                 Uses v-show (not v-if) so an already-open nested dropdown (teleported
                 elsewhere in the DOM) isn't torn down when the mouse leaves this row.
                 A local "fast-row" class is used instead of bootstrap's d-flex, whose
                 `display: flex !important` would otherwise beat v-show's inline style. -->
            <div v-show="hoverGroup" class="fast-row">
                <div v-if="!hasSubgroups" class="ms-1">
                    <WithToolTip message="dropdown.stamp.paint_group">
                        <StampDropdown :images="getImages" :no-border="true" style="font-size: 14px;"
                            :show-number="true" />
                    </WithToolTip>
                </div>

                <div class="ms-1" v-if="!hasSubgroups">
                    <ActionButton action="group" :defer="true" :busy="props.manager.isClustering(group.id)"
                        @submit="cluster" />
                </div>
                <div class="ms-1">
                    <ActionButton2 :no-border="true" action="execute" :defer="true"
                        :busy="props.manager.isClustering(group.id)" @submit="cluster">
                        <div class="bi bi-terminal"
                            style="position: relative; font-size: 14px; padding: 0px 5px 0 4px;">
                        </div>
                    </ActionButton2>
                </div>
            </div>

        </template>
    </div>
</template>

<style scoped>
.fast-row {
    display: flex;
    align-items: center;
}

.close-children {
    font-size: 11px;
    cursor: pointer;
}

.group-line {
    /* position: relative; */
    height: 30px;
    /* line-height: 25px; */
    align-items: center;
}

.group-line-border {
    height: 30px;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
}

.active {
    border-left: 1px solid blue;
}

.cluster-close {
    font-size: 14px;
    padding: 0px 3px;
    /* line-height: 16px; */
    /* color: grey; */
    /* border: 1px solid var(--border-color); */
}

.opt-btn {
    font-size: 14px;
    padding: 0px 5px;
    line-height: 20px;
}

.opt-menu {
    padding: 4px;
    white-space: nowrap;
    min-width: 170px;
}

.opt-row {
    display: flex;
    align-items: center;
    width: 100%;
    box-sizing: border-box;
    padding: 3px 6px;
    border-radius: 4px;
    white-space: nowrap;
    cursor: pointer;
}

.opt-row:hover {
    background-color: var(--grey);
}

/* ActionButton2's trigger is nested inside its own flex wrappers (.main2, then
   WithToolTip's ".text-nowrap.d-flex", then a plain div around the slot). Flex
   items don't stretch to fill their container by default, so without this the
   opt-row's own `width: 100%` has nothing full-width to resolve against and
   the hover highlight only covers the icon+label content. Force each wrapper
   in that chain to stretch so opt-row can actually fill the menu row. */
.opt-menu :deep(.main2) {
    width: 100%;
}

.opt-menu :deep(.main2 .text-nowrap.d-flex) {
    flex: 1;
}

.opt-menu :deep(.main2 .text-nowrap.d-flex > div) {
    flex: 1;
    display: flex;
}

/* Same issue for StampDropdown and the generic Dropdown wrapper divs
   (both use "m-0 p-0" on their root/button elements): they're plain
   blocks so they'd normally stretch on their own, but sit inside the
   flex chains above, so they also need an explicit full-width rule. */
.opt-menu :deep(.m-0.p-0) {
    width: 100%;
    display: block;
}

.opt-icon {
    width: 22px;
    text-align: center;
    font-size: 14px;
}

.opt-label {
    margin-left: 8px;
    font-size: 14px;
    white-space: nowrap;
}
</style>
