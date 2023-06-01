<script setup lang="ts">
import { reactive, computed, watch, onMounted, ref, unref, nextTick } from 'vue';
import ImageGroup from './ImageGroup.vue';
import { globalStore } from '../../data/store';
import { computeGroupFilter } from '@/utils/filter';
import { Group, GroupIndex, Image, PropertyType, Tab, GroupData } from '@/data/models';
import { DefaultDict } from '@/utils/helpers'
import PaginatedImages from './PaginatedImages.vue';
import ContentFilter from './ContentFilter.vue';
import { sortGroupTree, sortImages } from '@/utils/sort';
import ImageList from './ImageList.vue';

import moment from 'moment';

const props = defineProps({
    tab: Object as () => Tab,
    height: Number
})

const filterElem = ref(null)
const hrElem = ref(null)
const testElem = ref(null)

const scrollerWidth = ref(0)

const filters = computed(() => props.tab.data.filter)
const groups = computed(() => props.tab.data.groups)
const sorts = computed(() => props.tab.data.sortList)
const scrollerHeight = computed(() => {
    if (filterElem.value && hrElem.value) {
        return props.height - filterElem.value.clientHeight - hrElem.value.clientHeight - 5
    }
    return 0
})

const groupData = reactive({
    root: undefined,
    index: {},
    order: []
}) as GroupData

const imageGroups = reactive({}) as Group

const filteredImages = computed(() => {
    let images = Object.values(globalStore.images)

    if (Object.keys(props.tab.data.selectedFolders).length > 0) {
        let folderIds = Object.keys(props.tab.data.selectedFolders).map(Number)
        let allIds = [...folderIds] as Array<number>
        folderIds.forEach(id => allIds.push(...globalStore.getFolderChildren(id)))
        if (allIds.length > 0) {
            images = images.filter(img => img.paths.some((p: any) => allIds.includes(Number(p))))
        }
    }

    let filtered = images.filter(img => computeGroupFilter(img, filters.value))

    if (sorts.value.length > 0) {
        filtered = sortImages(filtered, globalStore.properties[sorts.value[0].property_id])
        if (!sorts.value[0].ascending) {
            filtered.reverse()
        }
    }

    return filtered
})
function computeGroups(force = false) {
    console.log('compute groups')
    let index = {} as GroupIndex
    let rootGroup = generateGroups(index)
    // console.log(rootGroup)
    // Object.assign(imageGroups, rootGroup)
    // if (!force) {
    //     Object.assign(imageGroups, replaceIfChanged(imageGroups, rootGroup))
    // }
    // else {
    //     Object.assign(imageGroups, rootGroup)
    // }

    for (let id in index) {
        index[id] = mergeGroup(index[id])
    }

    groupData.index = index
    groupData.root = rootGroup
    groupData.order = []
    sortGroupTree(groupData.root, groupData.order)
}

function mergeGroup(update: Group) {
    let index = groupData.index
    // console.log('merge: ' + update.id)
    
    let id = update.id

    if (index[id] == undefined) {
        return update
    }
    // console.log('closed: ' + index[id].closed)
    update.closed = index[id].closed
    let childrenIds = index[id].children
    if (!childrenIds || childrenIds.length == 0) {
        return update
    }

    let children = childrenIds.map(id => index[id]).filter(c => c != undefined).filter(c => c.propertyId == undefined)
    if (children.length > 0) {
        update.children = children.map(c => c.id)
        update.groups = children
    }
    return update
}

function isNode(group: Group) {
    return group.images && group.images.length == 0 && Array.isArray(group.groups) && group.groups.length > 0
}
function isLeaf(group: Group) {
    return group.images && group.images.length > 0
}

function replaceIfChanged(oldGroup: Group, newGroup: Group) {
    if (!oldGroup) {
        return newGroup
    }

    let changed = false
    if (isNode(oldGroup) && isNode(newGroup)) {
        console.log('isnode')
        if (oldGroup.propertyId != newGroup.propertyId || oldGroup.name != newGroup.name || oldGroup.count != newGroup.count) {
            changed = true
        }
    }
    else if (isLeaf(oldGroup) && isLeaf(newGroup)) {
        console.log('isleaf')
        if (oldGroup.propertyId == newGroup.propertyId && oldGroup.count == newGroup.count && oldGroup.name == oldGroup.name) {
            let oldImgs = {} as any
            oldGroup.images.forEach(img => oldImgs[img.sha1] = true)
            for (let img of newGroup.images) {
                if (!oldImgs[img.sha1]) {
                    changed = true
                    break
                }
            }
        }
        else {
            changed = true
        }
    }
    // type of nodes dont match
    else {
        changed = true
    }
    if (changed) {
        return newGroup
    }
    if (isLeaf(oldGroup)) {
        let imageOrder = newGroup.images.map(i => i.sha1)
        let oldImgs = {} as any
        oldGroup.images.forEach(img => oldImgs[img.sha1] = img)
        oldGroup.images = imageOrder.map(sha1 => oldImgs[sha1])
        return oldGroup
    }

    let oldSubGroups = {} as { [k: string]: Group }
    oldGroup.groups.forEach(g => oldSubGroups[g.id] = g)

    oldGroup.groups = newGroup.groups.map(g => replaceIfChanged(oldSubGroups[g.id], g))

    return oldGroup
}

function generateGroups(index: GroupIndex) {
    let rootGroup = {
        name: 'All',
        images: filteredImages.value,
        groups: undefined,
        count: filteredImages.value.length,
        propertyId: undefined,
        id: '0',
        depth: 0,
        parentId: undefined
    } as Group
    if (groups.value.length > 0) {
        rootGroup = computeSubgroups(rootGroup, groups.value, index)
    }
    index[rootGroup.id] = rootGroup
    return rootGroup
}



function computeSubgroups(parentGroup: Group, groupList: number[], index: GroupIndex) {
    let images = parentGroup.images
    let propertyId = groupList[0]
    let groups = new DefaultDict(Array) as { [k: string | number]: any }
    let type = globalStore.properties[propertyId].type

    for (let img of images) {
        let value = propertyId in img.properties ? img.properties[propertyId].value : "undefined"
        if (value == null || value == '') {
            value = undefined
        }
        if (type == PropertyType.checkbox && value != true) {
            value = false
        }
        if (Array.isArray(value)) {
            value.forEach((v: any) => groups[v].push(img))
        }
        if (type == PropertyType.date){
            groups[moment(value).format('YYYY/MM')].push(img)
        }
        else {
            groups[value].push(img)
        }
    }
    let res = []
    for (let group in groups) {
        let newGroup = {
            name: group,
            images: groups[group],
            groups: undefined,
            count: groups[group].length,
            propertyId: propertyId,
            id: parentGroup.id + '-' + propertyId + '-' + group,
            depth: parentGroup.depth + 1,
            parentId: parentGroup.id
        } as Group
        res.push(newGroup)
    }

    if (groupList.length > 1) {
        res.map(g => computeSubgroups(g, groupList.slice(1), index))
    }

    parentGroup.groups = res
    parentGroup.children = res.map(g => g.id)
    parentGroup.images = []
    res.forEach(g => index[g.id] = g)
    return parentGroup
}

onMounted(computeGroups)
onMounted(() => {
    scrollerWidth.value = hrElem.value.clientWidth
    window.addEventListener('resize', () => {
        nextTick(() => scrollerWidth.value = hrElem.value.clientWidth)
    })
})

watch(props, () => {
    globalStore.updateTab(props.tab)
}, { deep: true })

watch(filteredImages, () => computeGroups(), { deep: true })
watch(groups, () => computeGroups(), { deep: true })
watch(sorts, () => computeGroups(), { deep: true })


function log(value: any) {
    console.log(testElem.value.clientHeight)
}

</script>

<template>
    <div class="p-2" ref="filterElem">
        <ContentFilter :tab="props.tab" @compute-ml="" />
    </div>
    <hr class="custom-hr" ref="hrElem" />
    <!-- <button @click="testElem.scroll()">Scroll to bottom</button> -->
    <div v-if="scrollerWidth > 0" style="margin-left: 10px;">
        <ImageList :data="groupData" :image-size="props.tab.data.imageSize" :height="scrollerHeight - 20"
            ref="testElem" :width="scrollerWidth - 10" />
    </div>
    <!-- <div class="ms-2 mt-2">
        <div v-if="groupList.length && groupList[0].name == '__all__'">
            <PaginatedImages :images="groupList[0].images" :imageSize="props.tab.data.imageSize" :groupId="'0'" />
        </div>
        <div v-else>
            <div v-for="(group, index) in groupList">
                <ImageGroup :leftAlign="true" :group="group" :imageSize="props.tab.data.imageSize"
                    :group-id="String(index)" />
            </div>
        </div>
    </div> -->
</template>