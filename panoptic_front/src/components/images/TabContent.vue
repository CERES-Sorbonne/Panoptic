<script setup lang="ts">
import { reactive, computed, watch, onMounted, ref } from 'vue';
import ImageGroup from './ImageGroup.vue';
import { globalStore } from '../../data/store';
import { computeGroupFilter } from '@/utils/filter';
import { Group, Image, PropertyType, Tab } from '@/data/models';
import { DefaultDict } from '@/utils/helpers'
import PaginatedImages from './PaginatedImages.vue';
import ContentFilter from './ContentFilter.vue';
import { sortImages } from '@/utils/sort';

const props = defineProps({
    tab: Object as () => Tab
})

const filters = computed(() => props.tab.data.filter)
const groups = computed(() => props.tab.data.groups)
const sorts = computed(() => props.tab.data.sortList)

const imageGroups = reactive({}) as Group
const groupList = computed(() => {
    if(!imageGroups.id) 
        return []
    return [imageGroups]
})

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
function computeGroups(force=true) {
    console.log('compute groups')
    let rootGroup = generateGroups()
    console.log(rootGroup)
    if(!force) {
        Object.assign(imageGroups, replaceIfChanged(imageGroups, rootGroup))
    }
    else {
        Object.assign(imageGroups, rootGroup)
    }
    
}
function isNode(group: Group) {
    return group.images && group.images.length == 0 && Array.isArray(group.groups) && group.groups.length > 0
}
function isLeaf(group: Group) {
    return group.images && group.images.length > 0
}

function replaceIfChanged(oldGroup: Group, newGroup: Group) {
    if(!oldGroup) {
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
    if(changed) {
        return newGroup
    }
    if(isLeaf(oldGroup)) {
        let imageOrder = newGroup.images.map(i => i.sha1)
        let oldImgs = {} as any
        oldGroup.images.forEach(img => oldImgs[img.sha1] = img)
        oldGroup.images = imageOrder.map(sha1 => oldImgs[sha1])
        return oldGroup
    }

    let oldSubGroups = {} as {[k:string]: Group}
    oldGroup.groups.forEach(g => oldSubGroups[g.id] = g)

    oldGroup.groups = newGroup.groups.map(g => replaceIfChanged(oldSubGroups[g.id], g))

    return oldGroup
}

function generateGroups() {
    let rootGroup = {
        name: 'All',
        images: filteredImages.value,
        groups: undefined,
        count: filteredImages.value.length,
        propertyId: undefined,
        id: '__all__'
    } as Group
    if (groups.value.length > 0) {
        rootGroup = computeSubgroups(rootGroup, groups.value)
    }
    return rootGroup
}



function computeSubgroups(parentGroup: Group, groupList: number[]) {
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
        else {
            groups[value].push(img)
        }
    }
    let res = []
    for (let group in groups) {
        res.push({
            name: group,
            images: groups[group],
            groups: undefined,
            count: groups[group].length,
            propertyId: propertyId,
            id: propertyId + '-' + group
        } as Group)
    }

    if (groupList.length > 1) {
        res.map(g => computeSubgroups(g, groupList.slice(1)))
    }

    parentGroup.groups = res
    parentGroup.images = []
    return parentGroup
}

onMounted(computeGroups)


watch(props, () => {
    globalStore.updateTab(props.tab)
}, { deep: true })

watch(filteredImages, () => computeGroups(), { deep: true })
watch(groups, () => computeGroups(), { deep: true })
watch(sorts, () => computeGroups(), { deep: true })

</script>

<template>
    <div class="m-2">
        <ContentFilter :tab="props.tab" @compute-ml="" />
    </div>
    <hr class="custom-hr" />
    <div class="ms-2 mt-2">
        <div v-if="groupList.length && groupList[0].name == '__all__'">
            <PaginatedImages :images="groupList[0].images" :imageSize="props.tab.data.imageSize" :groupId="'0'" />
        </div>
        <div v-else>
            <div v-for="(group, index) in groupList">
                <ImageGroup :leftAlign="true" :group="group" :imageSize="props.tab.data.imageSize"
                    :group-id="String(index)" />
            </div>
        </div>
    </div>
</template>