<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import StampDropdown from '@/components/inputs/StampDropdown.vue'
import PropertyValue from '@/components/properties/PropertyValue.vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import wTT from '../../tooltips/withToolTip.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import { Group, GroupManager, GroupTree, GroupType, buildGroup } from '@/core/GroupManager'
import { DbCommit, GroupLine, GroupResult, Instance, InstancePropertyValue, Property, PropertyMode, PropertyType, Sha1ToInstances, Tag, buildTag } from '@/data/models'
import ActionButton from '@/components/actions/ActionButton.vue'
import { useDataStore } from '@/data/dataStore'
import { allChildrenSha1Groups } from '@/utils/utils'

const data = useDataStore()

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
const images = computed(() => props.item.data.images)
const subgroups = computed(() => props.item.data.children ?? [])
const hasImages = computed(() => props.item.data.images.length > 0)
const hasSubgroups = computed(() => {
    return props.item.data.children.length > 0 && props.item.data.subGroupType != GroupType.Sha1
})
const properties = computed(() => props.item.data.meta.propertyValues.map(v => data.properties[v.propertyId]))
const propertyValues = computed(() => props.item.data.meta.propertyValues)
const closed = computed(() => props.item.data.view.closed)
const hasOpenChildren = computed(() => props.item.data.children.some(c => !c.view.closed))

const selected = computed(() => !props.item.data.images.some(i => !props.manager.selectedImages.value[i.id]))

const groupName = computed(() => {
    if (props.item.data.type == GroupType.All) return 'All'
    if (props.item.data.type == GroupType.Cluster) return props.item.data.name ?? ('Cluster ' + props.item.data.parentIdx)
    return 'tmp name'
})

const someValue = computed(() => props.item.data.meta.propertyValues.some(v => v.value != undefined))

const instancesForExecute = computed(() => {
    const selected = images.value.filter(i => props.manager.selectedImages.value[i.id])
    if(selected.length) {
        return selected
    }
    return images.value
})

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
        // props.groupIndex[props.item.id].closed = false
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
    // props.manager.onChange.emit()
    emits('group:close', subgroups.value.map((g: Group) => g.id))
}

function openChildren() {
    subgroups.value.forEach((g: Group) => props.manager.openGroup(g.id))
    // props.manager.onChange.emit()
    emits('group:open', subgroups.value.map((g: Group) => g.id))
}

const saving = ref(false)
async function saveHirachy() {
    if (saving.value) return

    saving.value = true
    const children = group.value.children
    const mode = allChildrenSha1Groups(group.value) ? PropertyMode.sha1 : PropertyMode.id
    console.log(mode)
    const property: Property = {id: -1, name: 'Clustering', type: PropertyType.multi_tags, mode: mode}
    let id = 0
    const idFunc = () => { id -= 1; return id }
    const tagToImages: { [tagId: number]: Instance[] } = {}
    const tags = childrenToTags(children, idFunc, undefined, tagToImages, property.id)

    const instanceValues: InstancePropertyValue[] = []
    for (let tagId in tagToImages) {
        const images = tagToImages[tagId]
        for (let img of images) {
            instanceValues.push({ propertyId: property.id, instanceId: img.id, value: [Number(tagId)] })
        }
    }

    // await data.setPropertyValues(instanceValues, [])

    const commit: DbCommit = {
        properties: [property],
        tags: tags,
        instanceValues: instanceValues
    }

    await data.sendCommit(commit)

    saving.value = false
}

function childrenToTags(children: Group[], idFunc: Function, parentTag: Tag, tagToImages: { [tagId: number]: Instance[] }, propertyId: number) {
    const res: Tag[] = []
    const prefix = parentTag?.value ?? ('Clustering_' + children.length)
    const parents = []
    if(parentTag) {
        // parents.push(...parentTag.parents, parentTag.id)
        parents.push(parentTag.id)
    }

    for (let i = 0; i < children.length; i++) {
        const child = children[i]
        const value = prefix + '.' + i
        const tag = buildTag(idFunc(), propertyId, value, parents)
        res.push(tag)

        if (child.children.length && child.subGroupType != GroupType.Sha1) {
            const subRes = childrenToTags(child.children, idFunc, tag, tagToImages, propertyId)
            res.push(...subRes)
        } else {
            tagToImages[tag.id] = child.images
        }
    }
    return res
}

</script>

<template>
    <div class="d-flex flex-row group-line m-0 p-0 overflow-hidden" @mouseenter="hoverGroup = true"
        @mouseleave="hoverGroup = false">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2"
            @click="$emit('scroll', parentId)" @mouseenter="$emit('hover', parentId)" @mouseleave="$emit('unhover')">
            <div class="group-line-border" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <div @click="toggleClosed" class="align-self-center me-2" style="cursor: pointer;">
            <i v-if="closed" class="bi bi-caret-right-fill" style="margin-left: 1px;"></i>
            <i v-else class="bi bi-caret-down-fill" style="margin-left: 1px;"></i>
        </div>
        <div class="me-1">
            <SelectCircle :small="true" :model-value="selected"
                @update:model-value="emits('select', group.id)" />
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
        <div class="align-self-center me-2 text-secondary" style="font-size: 11px;">{{ group.images.length }} Images
        </div>
        <div v-if="subgroups.length" class="align-self-center me-2 text-secondary" style="font-size: 11px;">{{
        subgroups.length }} {{ $t('main.view.groupes_nb') }}</div>

        <div class="d-flex flex-row align-self-center me-2" v-if="!closed && !props.hideOptions">
            <div v-if="!hasSubgroups" class="ms-2">
                <StampDropdown :images="images" />
            </div>

            <div class="ms-2" v-if="!hasSubgroups">
                <ActionButton action="group" :images="group.images" style="font-size: 10px;"
                    @groups="addClusters" />
            </div>
            <div class="ms-2">
                <ActionButton action="execute" :images="instancesForExecute" style="font-size: 10px;"
                    @groups="addClusters" />
            </div>

            <div v-if="(hasImages) && !hasSubgroups && !(group.type == GroupType.Cluster) && someValue"
                class="ms-2">
                <wTT message="main.recommand.tooltip">
                    <div class="button" @click="recommandImages">{{ $t('main.recommand.title') }}</div>
                </wTT>
            </div>
            <wTT v-if="group.subGroupType == GroupType.Cluster" class="ms-2" message="btn.close-clusters">
                <div class="sbb cluster-close" @click="clear">X Clusters</div>
            </wTT>

            <wTT v-if="group.subGroupType == GroupType.Cluster" class="ms-2" message="btn.save-clusters">
                <div class="sbb cluster-close" @click="saveHirachy">
                    <span style="position: relative; top: 1px">
                        <i class="bi bi-floppy2-fill" style="margin-right: 3px;"></i>
                        <i v-if="!saving" class="bi bi-diagram-3"></i>
                        <div v-else class="spinner-border spinner-border-sm text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </span>
                </div>
            </wTT>
            <!-- <span v-if="group.isSha1Group">lala</span> -->
        </div>

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
}

.group-line-border {
    height: 100%;
    border-left: 1px solid var(--border-color);
    padding-left: 10px;
}

.active {
    border-left: 1px solid blue;
}

.cluster-close {
    font-size: 10px;
    padding: 0px 3px;
    line-height: 16px;
    /* color: grey; */
    border: 2px solid var(--border-color);
}
</style>