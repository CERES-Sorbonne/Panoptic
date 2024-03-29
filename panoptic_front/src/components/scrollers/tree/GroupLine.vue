<script setup lang="ts">
import { computed, ref } from 'vue'
import StampDropdown from '@/components/inputs/StampDropdown.vue'
import PropertyValue from '@/components/properties/PropertyValue.vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import wTT from '../../tooltips/withToolTip.vue'
import ClusterBadge from '@/components/cluster/ClusterBadge.vue'
import ClusterButton from './ClusterButton.vue'
import { Group, GroupManager, GroupResult, GroupType, UNDEFINED_KEY, buildGroup } from '@/core/GroupManager'
import { GroupLine } from '@/data/models'
import { useProjectStore } from '@/data/projectStore'
import { computeMLGroups } from '@/utils/utils'
import ActionButton from '@/components/actions/ActionButton.vue'

const store = useProjectStore()

const props = defineProps({
    item: Object as () => GroupLine,
    manager: GroupManager,
    parentIds: Array<string>,
    hoverBorder: String,
    data: Object as () => GroupResult,
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
const properties = computed(() => group.value.meta.propertyValues.map(v => store.data.properties[v.propertyId]))
const propertyValues = computed(() => group.value.meta.propertyValues)
const closed = computed(() => group.value.view.closed)
const hasOpenChildren = computed(() => props.item.data.children.some(c => !c.view.closed))


const groupName = computed(() => {
    if (group.value.type == GroupType.All) return 'All'
    if (group.value.type == GroupType.Cluster) return 'Cluster ' + group.value.parentIdx
    return 'tmp name'
})

const someValue = computed(() => group.value.meta.propertyValues.some(v => v.value != UNDEFINED_KEY))

async function addClusters(groupResult) {
    console.log(groupResult)
    const groups = groupResult.groups.map((group, index) => {
        const instances = group.ids.map(i => store.data.images[i])
        const res = buildGroup('cluster:' + String(index) + ':' + props.item.id, instances, GroupType.Cluster)
        res.meta.score = Math.round(group.score)
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
        props.manager.toggleGroup(group.value.id, true)
        emits('group:open', props.item.id)
    }
    else {
        props.manager.toggleGroup(group.value.id, true)
        emits('group:close', props.item.id)
    }
}

function closeChildren() {
    subgroups.value.forEach((g: Group) => props.manager.closeGroup(g.id))
    props.manager.onChange.emit()
    emits('group:close', subgroups.value.map((g: Group) => g.id))
}

</script>

<template>
    <div class="d-flex flex-row group-line m-0 p-0 overflow-hidden" @mouseenter="hoverGroup = true"
        @mouseleave="hoverGroup = false">
        <div v-for="parentId in props.parentIds" style="cursor: pointer;" class="ps-2" @click="$emit('scroll', parentId)"
            @mouseenter="$emit('hover', parentId)" @mouseleave="$emit('unhover')">
            <div class="group-line-border" :class="props.hoverBorder == parentId ? 'active' : ''"></div>
        </div>
        <div @click="toggleClosed" class="align-self-center me-2" style="cursor: pointer;">
            <i v-if="closed" class="bi bi-caret-right-fill" style="margin-left: 1px;"></i>
            <i v-else class="bi bi-caret-down-fill" style="margin-left: 1px;"></i>
        </div>
        <div class="me-1">
            <SelectCircle :small="true" :model-value="group.view.selected"
                @update:model-value="emits('select', group.id)" />
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
        <div class="align-self-center me-2 text-secondary" style="font-size: 11px;">{{ group.images.length }} Images</div>
        <div v-if="subgroups.length" class="align-self-center me-2 text-secondary" style="font-size: 11px;">{{
            subgroups.length }} {{ $t('main.view.groupes_nb') }}</div>

        <div class="d-flex flex-row align-self-center me-2" v-if="!closed && !props.hideOptions">
            <div v-if="!hasSubgroups" class="ms-2">
                <StampDropdown :images="images" />
            </div>
            <div class="ms-2" v-if="!hasSubgroups">
                <!-- <wTT message="main.view.group_clusters_tooltip">
                    <ClusterButton v-model="props.item.nbClusters" @click="computeClusters" />
                </wTT> -->
                <ActionButton action="group" :image-ids="images.map(i => i.id)" style="font-size: 10px;"
                    @result="addClusters" />
            </div>
            <div v-if="(hasImages || hasPiles) && !hasSubgroups" style="margin-left: 2px;">

            </div>
            <div v-if="(hasImages || hasPiles) && !hasSubgroups && !(group.type == GroupType.Cluster) && someValue"
                class="ms-2">
                <wTT message="main.recommand.tooltip">
                    <div class="button" @click="recommandImages">{{ $t('main.recommand.title') }}</div>
                </wTT>
            </div>
            <div v-if="group.subGroupType == GroupType.Cluster" class="ms-2">
                <div class="sbb cluster-close" @click="clear">x clusters</div>
            </div>
        </div>

        <div v-if="hasSubgroups && hoverGroup && hasOpenChildren"
            class="ms-1 text-secondary align-self-center close-children" @click="closeChildren">
            {{ $t('main.view.collapse') }}
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
    font-size: 12px;
    padding: 0px 3px;
    line-height: 16px;
    color: grey;
    border: 2px solid var(--border-color);
}
</style>