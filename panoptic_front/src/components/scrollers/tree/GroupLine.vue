<script setup lang="ts">
import { computed, ref } from 'vue'
import StampDropdown from '@/components/inputs/StampDropdown.vue'
import PropertyValue from '@/components/properties/PropertyValue.vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import wTT from '../../tooltips/withToolTip.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import { Group, GroupManager, GroupTree, GroupType, buildGroup } from '@/core/GroupManager'
import { DbCommit, GroupLine, GroupResult, Instance, InstancePropertyValue, Property, PropertyMode, PropertyType, Tag, buildTag } from '@/data/models'
import ActionButton from '@/components/actions/ActionButton.vue'
import { useDataStore } from '@/data/dataStore'

const data = useDataStore()

const props = defineProps({
    item: Object as () => GroupLine,
    manager: GroupManager,
    parentIds: Array<number>,
    hoverBorder: Number,
    data: Object as () => GroupTree,
    hideOptions: Boolean
})

const emits = defineEmits(['hover', 'unhover', 'scroll', 'group:close', 'group:open', 'group:update', 'recommend', 'select'])

const hoverGroup = ref(false)
const group = computed(() => props.item.data)
const images = computed(() => group.value.images)
const piles = computed(() => undefined /*props.item.data.imagePiles*/)
const subgroups = computed(() => group.value.children)
const hasImages = computed(() => images.value.length > 0)
const hasPiles = computed(() => Array.isArray(piles.value))
const hasSubgroups = computed(() => subgroups.value.length > 0 && group.value.subGroupType != GroupType.Sha1)
const properties = computed(() => group.value.meta.propertyValues.map(v => data.properties[v.propertyId]))
const propertyValues = computed(() => group.value.meta.propertyValues)
const closed = computed(() => group.value.view.closed)
const hasOpenChildren = computed(() => props.item.data.children.some(c => !c.view.closed))

const selected = computed(() => !props.item.data.images.some(i => !props.manager.selectedImages.value[i.id]))

const groupName = computed(() => {
    if (group.value.type == GroupType.All) return 'All'
    if (group.value.type == GroupType.Cluster) return group.value.name ?? ('Cluster ' + group.value.parentIdx)
    return 'tmp name'
})

const someValue = computed(() => group.value.meta.propertyValues.some(v => v.value != undefined))

const instancesForExecute = computed(() => {
    const selected = images.value.filter(i => props.manager.selectedImages.value[i.id])
    if(selected.length) {
        return selected
    }
    return images.value
})

async function addClusters(clusters: GroupResult[]) {
    const groups = clusters.map((group, index) => {
        const instances = group.ids.map(i => data.instances[i])
        const res = buildGroup(data.getTmpId(), instances, GroupType.Cluster)
        res.meta.score = Math.round(group.score)
        res.name = group.name
        return res
    })
    props.manager.addCustomGroups(group.value.id, groups, true)
}

function clear() {
    props.manager.delCustomGroups(group.value.id, true)
}

async function recommandImages() {
    emits('recommend', props.item.data.id)
}

function toggleClosed() {
    if (closed.value) {
        // props.groupIndex[props.item.id].closed = false
        props.manager.toggleGroup(group.value.id, false)
        emits('group:open', props.item.id)
    }
    else {
        props.manager.toggleGroup(group.value.id, false)
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
    const property: Property = {id: -1, name: 'Clustering', type: PropertyType.multi_tags, mode: PropertyMode.id}
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
        parents.push(...parentTag.parents, parentTag.id)
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
            <ClusterBadge :value="group.meta.score" />
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

            <div v-if="(hasImages || hasPiles) && !hasSubgroups && !(group.type == GroupType.Cluster) && someValue"
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