<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import StampDropdown from '@/components/inputs/StampDropdown.vue'
import PropertyValue from '@/components/properties/PropertyValue.vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import wTT from '../../tooltips/withToolTip.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import { Group, GroupManager, GroupTree, GroupType, buildGroup } from '@/core/GroupManager'
import { DbCommit, GroupLine, GroupResult, ImagePropertyValue, Instance, InstancePropertyValue, Property, PropertyMode, PropertyType, Sha1ToInstances, Tag, buildTag } from '@/data/models'
import ActionButton from '@/components/actions/ActionButton.vue'
import { useDataStore } from '@/data/dataStore'
import { useColumnStore } from '@/data/columnStore' // <-- Imported columnStore
import { allChildrenSha1Groups } from '@/utils/utils'
import ActionButton2 from '@/components/actions/ActionButton2.vue'
import WithToolTip from '../../tooltips/withToolTip.vue'
import { apiAllocateTags } from '@/data/apiProjectRoutes'

const data = useDataStore()
const columnStore = useColumnStore() // <-- Initialized column store

const props = defineProps<{
    item: GroupLine
    manager: GroupManager
    parentIds: number[];
    hoverBorder: number,
    data: GroupTree,
    hideOptions: boolean
}>()

const emits = defineEmits(['hover', 'unhover', 'scroll', 'group:close', 'group:open', 'group:update', 'recommend', 'select'])

const hoverGroup = ref(false)
const group = computed(() => props.item.data)

const slots = computed(() => props.item.data.slots ?? [])

function getImages() {
    const ids = columnStore.instanceIds()
    const sha1s = columnStore.sha1s()
    return slots.value.map(slot => ({ id: ids[slot], imageUrl: data.baseImgUrl + 'by_size/' + sha1s[slot], sha1: sha1s[slot] }))
}

const subgroups = computed(() => props.item.data.children ?? [])
const hasImages = computed(() => slots.value.length > 0)

const hasSubgroups = computed(() => {
    return subgroups.value.length > 0 && props.item.data.subGroupType != GroupType.Sha1
})
const properties = computed(() => props.item.data.meta.propertyValues.map(v => data.properties[v.propertyId]))
const propertyValues = computed(() => props.item.data.meta.propertyValues)
const closed = computed(() => props.item.data.view.closed)
const hasOpenChildren = computed(() => props.item.data.children.some(c => !c.view.closed))

const selected = computed(() => {
    const ids = columnStore.instanceIds()
    return !slots.value.some(slot => !props.manager.selectedImages.value[ids[slot]])
})

const groupName = computed(() => {
    if (props.item.data.type == GroupType.All) return 'All'
    if (props.item.data.type == GroupType.Cluster) return props.item.data.name ?? ('Cluster ' + props.item.data.parentIdx)
    return 'tmp name'
})

const someValue = computed(() => props.item.data.meta.propertyValues.some(v => v.value != undefined))

function instancesForExecute() {
    const ids = columnStore.instanceIds()
    const sha1s = columnStore.sha1s()
    const selected = slots.value.filter(slot => props.manager.selectedImages.value[ids[slot]])
    if (selected.length) {
        return selected.map(slot => ({ id: ids[slot], imageUrl: data.baseImgUrl + 'by_size/' + sha1s[slot] }))
    }
    return getImages()
}

async function addClusters(groups: Group[]) {
    props.manager.addCustomGroups(props.item.data.id, groups, true)
}

function clear() {
    props.manager.delCustomGroups(props.item.data.id, true)
}

async function recommandImages() {
    emits('recommend', props.item.data.id)
}

function toggleClosed() {
    if (closed.value) {
        props.manager.toggleGroup(props.item.data.id, false)
        emits('group:open', props.item.id)
    }
    else {
        props.manager.toggleGroup(props.item.data.id, false)
        emits('group:close', props.item.id)
    }
}

function closeChildren() {
    subgroups.value.forEach((g: Group) => props.manager.closeGroup(g.id))
    emits('group:close', subgroups.value.map((g: Group) => g.id))
}

function openChildren() {
    subgroups.value.forEach((g: Group) => props.manager.openGroup(g.id))
    emits('group:open', subgroups.value.map((g: Group) => g.id))
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
        const hasSubgroups = child.children.length > 0 && child.subGroupType != GroupType.Sha1
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
        const hasSubgroups = child.children.length > 0 && child.subGroupType != GroupType.Sha1

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
    <div class="d-flex flex-row group-line m-0 p-0 overflow-hidden">
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
            <div v-if="!hasSubgroups" class="ms-1 sbb">
                <WithToolTip message="dropdown.stamp.paint_group">
                    <StampDropdown :images="getImages" :no-border="true" style="font-size: 14px;" :show-number="true" />
                </WithToolTip>
            </div>

            <div class="ms-1" v-if="!hasSubgroups">
                <ActionButton action="group" :images="getImages" @groups="addClusters" />
            </div>
            <div class="ms-1">
                <ActionButton2 action="execute" :images="instancesForExecute" @groups="addClusters">
                    <div class="bi bi-terminal" style="position: relative; font-size: 14px; padding: 0px 5px 0 4px;">
                    </div>
                </ActionButton2>
            </div>

            <div v-if="(hasImages) && !hasSubgroups && !(group.type == GroupType.Cluster) && someValue" class="ms-2">
                <wTT message="main.recommand.tooltip">
                    <div class="button" @click="recommandImages">{{ $t('main.recommand.title') }}</div>
                </wTT>
            </div>
            <wTT v-if="group.subGroupType == GroupType.Cluster" class="ms-1" message="btn.save-clusters">
                <div class="sbb cluster-close" @click="saveHirachy()">
                    <span style="">
                        <i class="bi bi-floppy2-fill" style="margin-right: 3px;"></i>
                        <i v-if="!saving" class="bi bi-diagram-3"></i>
                        <div v-else class="spinner-border spinner-border-sm text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </span>
                </div>
            </wTT>
            <wTT v-if="group.subGroupType == GroupType.Cluster" class="ms-1" message="btn.save-clusters">
                <div class="sbb cluster-close" @click="saveHirachy(true)">
                    <span style="">
                        <i class="bi bi-floppy2-fill" style="margin-right: 3px;"></i>
                        <div v-if="saving" class="spinner-border spinner-border-sm text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </span>
                </div>
            </wTT>
            <wTT v-if="group.subGroupType == GroupType.Cluster" class="ms-1 bbb" message="btn.close-clusters"
                style="font-size: 14px;">
                <div class="cluster-close" @click="clear"><i class="bi bi-x-lg" /></div>
            </wTT>
        </template>
    </div>
</template>

<style scoped>
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
</style>