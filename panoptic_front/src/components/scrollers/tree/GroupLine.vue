<script setup lang="ts">
import { ComputedRef, computed, inject, ref, watch } from 'vue'
import StampDropdown from '@/components/inputs/StampDropdown.vue'
import PropertyValue from '@/components/properties/PropertyValue.vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import { ClusterRequest, Group, GroupTree, GroupType } from '@/core/GroupManager'
import type { GroupInspector } from '@/core/group/inspector'
import { ImagePropertyValue, InstancePropertyValue, Property, PropertyMode, PropertyType, Tag, buildTag } from '@/data/models'
import { GroupLine } from '@/components/scrollers/types'
import ActionButton from '@/components/actions/ActionButton.vue'
import { useDataStore } from '@/data/stores/dataStore'
import { useColumnStore } from '@/data/stores/columnStore' // <-- Imported columnStore
import { allChildrenSha1Groups } from '@/utils/utils'
import ActionButton2 from '@/components/actions/ActionButton2.vue'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import WithToolTip from '../../tooltips/withToolTip.vue'
import { apiAllocateTags } from '@/data/api/projectApi'
import { clusterErrorText } from '@/core/group/ClusterManager'

const data = useDataStore()
const columnStore = useColumnStore() // <-- Initialized column store
const selectNamespace = inject<ComputedRef<string>>('selectNamespace', computed(() => 'global'))

const props = defineProps<{
    item: GroupLine
    manager: GroupInspector
    parentIds: number[];
    data: GroupTree,
    hideOptions: boolean
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'group:close', 'group:open', 'group:update', 'select', 'reco'])

const hoverGroup = ref(false)

// Number of fast-row dropdowns currently open. v-show alone isn't enough: once the mouse
// leaves the line the row gets `display: none`, its button's bounding rect collapses to
// 0x0, and floating-vue — which repositions on any content change, e.g. switching the
// function inside ActionButton2 — then anchors the (teleported, still open) popup at the
// top-left of the screen. Keeping the row laid out while a popup is open fixes that.
const openFastPopups = ref(0)
function onFastShow() { openFastPopups.value++ }
function onFastHide() { openFastPopups.value = Math.max(0, openFastPopups.value - 1) }

// The group tree is plain, non-reactive data: the manager's `version` ref is the only
// change signal. Every computed derived from the tree must read it, otherwise it caches
// its first value and refreshes only when some *other* reactive dep of this component
// happens to change (which is why e.g. the open/close-all button appeared late).
const version = computed(() => props.manager.version.value)

// The tree is mutated IN PLACE, so `props.item.data`, `.children` and `.slots` keep their
// identity across changes. A computed only notifies its dependents when its value changes by
// identity, so a computed returning one of those objects is a dead end: it recomputes, sees the
// same reference, and never invalidates anything downstream (this is why clearing a cluster left
// `hasSubgroups` true until an unrelated re-render). Everything the template reads must therefore
// be a SCALAR computed that reads `version` itself — never chained off an object-valued one.
const group = () => props.item.data

const slotCount = computed(() => (version.value, props.item.data.slots?.length ?? 0))

function getImages() {
    const ids = columnStore.instanceIds()
    const sha1s = columnStore.sha1s()
    const slots = props.item.data.slots ?? []
    return slots.map(slot => ({ id: ids[slot], imageUrl: data.baseImgUrl + 'by_size/' + sha1s[slot], sha1: sha1s[slot] }))
}

const subgroupCount = computed(() => (version.value, props.item.data.children?.length ?? 0))
const hasImages = computed(() => slotCount.value > 0)
const hasSubgroups = computed(() => subgroupCount.value > 0)

const properties = computed(() => (version.value, props.item.data.meta.propertyValues.map(v => data.properties[v.propertyId])))
const propertyValues = computed(() => (version.value, props.item.data.meta.propertyValues.slice()))
const closed = computed(() => (version.value, props.item.data.view.closed))
const hasOpenChildren = computed(() => (version.value, (props.item.data.children ?? []).some((c: Group) => !c.view.closed)))

const groupType = computed(() => (version.value, props.item.data.type))
const score = computed(() => (version.value, props.item.data.score?.value))

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

// A run that failed stops the spinner and leaves nothing on screen, so the button says why.
const clusterFailed = computed(() => {
    const error = props.manager.clusterError(props.item.data.id)
    return error ? `Clustering failed: ${clusterErrorText(error)}` : undefined
})

function clear() {
    props.manager.delCustomGroups(props.item.data.id, true)
}

// open/close mutate `view.closed` in place on the plain tree, so they must emit
// (bump `version`) — the scroller event alone rebuilds lines but leaves every
// tree-derived computed in this and every other line component stale. Bump first, then emit:
// the scroller rebuilds on the event and stamps the bumped version, which is what lets it skip
// the rebuild its version watcher would otherwise queue for the same change.
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
    const ids = (props.item.data.children ?? []).map((g: Group) => g.id)
    ids.forEach((id: number) => props.manager.closeGroup(id))
    props.manager.emitResult()
    emits('group:close', ids)
}

function openChildren() {
    const ids = (props.item.data.children ?? []).map((g: Group) => g.id)
    ids.forEach((id: number) => props.manager.openGroup(id))
    props.manager.emitResult()
    emits('group:open', ids)
}

const saving = ref(false)
// tree: tags keep the cluster hierarchy as parents
// flat: one tag per cluster without parents, images also carry the tags of their ancestor clusters
// leaves: only the leaf clusters become tags
type SaveMode = 'tree' | 'flat' | 'leaves'

async function saveClusters(saveMode: SaveMode) {
    if (saving.value) return
    saving.value = true

    const children = group().children
    const mode = allChildrenSha1Groups(group()) ? PropertyMode.sha1 : PropertyMode.id

    const property: Property = { id: -1, name: 'Clustering', type: PropertyType.multi_tags, mode: mode }
    const [realTagIds, realPropId] = await Promise.all([
        apiAllocateTags(countTags(children, saveMode)),
        data.sendCommit({ properties: [property] }).then(res => res.properties[0].id),
    ])

    let idx = 0
    const nextId = () => realTagIds[idx++]
    const imageTags: { id: number, tags: number[] }[] = []
    const tags = childrenToTags(children, nextId, 'Clustering_' + children.length, undefined, [], imageTags, realPropId, saveMode)

    const instanceValues: InstancePropertyValue[] = []
    const imageValues: ImagePropertyValue[] = []
    for (const img of imageTags) {
        if (mode == PropertyMode.id) {
            instanceValues.push({ propertyId: realPropId, instanceId: img.id, value: img.tags })
        } else {
            imageValues.push({ propertyId: realPropId, sha1: data.getSysField(img.id, 'sha1'), value: img.tags })
        }
    }

    await data.sendCommit({ tags, instanceValues, imageValues })
    saving.value = false
}

function countTags(children: Group[], saveMode: SaveMode): number {
    let count = 0
    for (const child of children) {
        if (child.children.length) {
            if (saveMode != 'leaves') count++
            count += countTags(child.children, saveMode)
        } else {
            count++
        }
    }
    return count
}

function childrenToTags(children: Group[], nextId: () => number, prefix: string, parentTag: Tag | undefined, ancestors: number[],
    imageTags: { id: number, tags: number[] }[], propertyId: number, saveMode: SaveMode) {
    const res: Tag[] = []
    const parentIds = parentTag && saveMode == 'tree' ? [parentTag.id] : []
    const ids = columnStore.instanceIds()

    for (let i = 0; i < children.length; i++) {
        const child = children[i]
        const name = prefix + '.' + i

        if (child.children.length && saveMode == 'leaves') {
            res.push(...childrenToTags(child.children, nextId, name, parentTag, ancestors, imageTags, propertyId, saveMode))
            continue
        }

        const tag = buildTag(nextId(), propertyId, name, parentIds)
        res.push(tag)
        if (child.children.length) {
            res.push(...childrenToTags(child.children, nextId, name, tag, [...ancestors, tag.id], imageTags, propertyId, saveMode))
        } else {
            const value = saveMode == 'flat' ? [tag.id, ...ancestors] : [tag.id]
            for (const slot of child.slots ?? []) imageTags.push({ id: ids[slot], tags: value })
        }
    }
    return res
}

</script>

<template>
    <div class="d-flex flex-row group-line overflow-hidden"
        @mouseenter="hoverGroup = true" @mouseleave="hoverGroup = false">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2"
            @click="$emit('scroll', parentId)" @mouseenter="$emit('hover', parentId)" @mouseleave="$emit('unhover')">
            <div class="group-line-border" :data-border-group="parentId"> </div>
        </div>
        <div @click="toggleClosed" class="align-self-center me-2" style="cursor: pointer;">
            <i v-if="closed" class="bi bi-caret-right-fill" style="margin-left: 0px;"></i>
            <i v-else class="bi bi-caret-down-fill" style="margin-left: 0px;"></i>
        </div>
        <div class="me-1">
            <SelectCircle :small="true" :model-value="selected" @update:model-value="emits('select', props.item.data.id)" />
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
        <div v-if="groupType == GroupType.Cluster" style="padding-top: 2.5px;" class="me-2">
            <ClusterBadge v-if="score != undefined" :value="Math.round(score)" :score="props.item.data.score" />
        </div>

        <div class="align-self-center me-2 text-secondary" style="font-size: 11px;"><span class="num">{{ slotCount }}</span> Images
        </div>

        <div v-if="subgroupCount" class="align-self-center me-2 text-secondary" style="font-size: 11px;"><span
            class="num">{{ subgroupCount }}</span> {{ $t('main.view.groupes_nb') }}</div>

        <template v-if="!closed && !props.hideOptions">
            <template v-if="isClusterGroup">
                <div class="ms-1">
                    <Dropdown :teleport="true">
                        <template #button>
                            <WithToolTip message="btn.save-clusters">
                                <div class="sb opt-btn">
                                    <div v-if="saving" class="spinner-border spinner-border-sm text-primary" role="status"></div>
                                    <i v-else class="bi bi-floppy2-fill" />
                                </div>
                            </WithToolTip>
                        </template>
                        <template #popup="{ hide }">
                            <div class="opt-menu">
                                <div class="opt-row" @click="saveClusters('tree'); hide();">
                                    <span class="opt-icon">
                                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" stroke="currentColor">
                                            <rect x="6" y="1" width="4" height="4" rx="1" stroke="none" />
                                            <path d="M8 5v3M3 8h10M3 8v3M13 8v3" fill="none" stroke-width="1.2" />
                                            <rect x="1" y="11" width="4" height="4" rx="1" stroke="none" />
                                            <rect x="11" y="11" width="4" height="4" rx="1" stroke="none" />
                                        </svg>
                                    </span>
                                    <span class="opt-label">{{ $t('btn.save-clusters-tree') }}</span>
                                </div>
                                <div class="opt-row" @click="saveClusters('flat'); hide();">
                                    <span class="opt-icon">
                                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                                            <rect x="0.5" y="6" width="4" height="4" rx="1" />
                                            <rect x="6" y="6" width="4" height="4" rx="1" />
                                            <rect x="11.5" y="6" width="4" height="4" rx="1" />
                                        </svg>
                                    </span>
                                    <span class="opt-label">{{ $t('btn.save-clusters-flat') }}</span>
                                </div>
                                <div class="opt-row" @click="saveClusters('leaves'); hide();">
                                    <span class="opt-icon">
                                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" stroke="currentColor">
                                            <rect x="6.5" y="1.5" width="3" height="3" rx="0.8" fill="none" stroke-dasharray="1.5 1" opacity="0.7" />
                                            <path d="M8 5v3M3 8h10M3 8v3M13 8v3" fill="none" stroke-width="1" stroke-dasharray="1.5 1.2" opacity="0.55" />
                                            <rect x="1" y="11" width="4" height="4" rx="1" stroke="none" />
                                            <rect x="11" y="11" width="4" height="4" rx="1" stroke="none" />
                                        </svg>
                                    </span>
                                    <span class="opt-label">{{ $t('btn.save-clusters-leaves') }}</span>
                                </div>
                            </div>
                        </template>
                    </Dropdown>
                </div>
                <div class="ms-1">
                    <WithToolTip message="btn.close-clusters">
                        <div class="sb opt-btn" @click="clear">
                            <i class="bi bi-x-lg" />
                        </div>
                    </WithToolTip>
                </div>
            </template>

            <!-- Options dropdown: always visible -->
            <div v-if="!isClusterGroup" class="ms-1">
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
                                :busy="props.manager.isClustering(props.item.data.id)" @submit="cluster">
                                <div class="opt-row">
                                    <span class="opt-icon"><i class="bi bi-intersect" /></span>
                                    <span class="opt-label">{{ $t('action.group') }}</span>
                                </div>
                            </ActionButton2>

                            <ActionButton2 action="execute" :no-border="true" :defer="true"
                                :busy="props.manager.isClustering(props.item.data.id)" @submit="cluster">
                                <div class="opt-row">
                                    <span class="opt-icon"><i class="bi bi-terminal" /></span>
                                    <span class="opt-label">{{ $t('action.execute') }}</span>
                                </div>
                            </ActionButton2>

                            <div v-if="!hasSubgroups" class="opt-row" @click="emits('reco', props.item.data.id); hide();">
                                <span class="opt-icon"><i class="bi bi-magic" /></span>
                                <span class="opt-label">{{ $t('main.menu.reco_tooltip') }}</span>
                            </div>

                        </div>
                    </template>
                </Dropdown>
            </div>

            <!-- Fast-access actions: visible only while hovering the group line.
                 Uses v-show (not v-if) so an already-open nested dropdown (teleported
                 elsewhere in the DOM) isn't torn down when the mouse leaves this row.
                 A local "fast-row" class is used instead of bootstrap's d-flex, whose
                 `display: flex !important` would otherwise beat v-show's inline style. -->
            <div v-show="hoverGroup || openFastPopups > 0" class="fast-row">
                <div v-if="!hasSubgroups" class="ms-1">
                    <WithToolTip message="dropdown.stamp.paint_group">
                        <StampDropdown :images="getImages" :no-border="true" style="font-size: 14px;"
                            :show-number="true" @show="onFastShow" @hide="onFastHide" />
                    </WithToolTip>
                </div>

                <div class="ms-1" v-if="!hasSubgroups">
                    <ActionButton action="group" :defer="true" :busy="props.manager.isClustering(props.item.data.id)"
                        :message="clusterFailed"
                        @submit="cluster" />
                </div>
                <div class="ms-1">
                    <ActionButton2 :no-border="true" action="execute" :defer="true"
                        :busy="props.manager.isClustering(props.item.data.id)" @submit="cluster"
                        @show="onFastShow" @hide="onFastHide">
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
    /* Already overflow-hidden, and every dropdown/tooltip here is teleported: containing it is
       free, and the hover row showing/hiding stays local to the line. Not `strict`: size
       containment would leave the width to whatever the scroller's item wrapper gives it. */
    contain: layout paint style;
    /* line-height: 25px; */
    align-items: center;
}

.group-line-border {
    height: 30px;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
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
