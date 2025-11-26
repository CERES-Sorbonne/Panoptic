<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { buildTag, Instance, ModalId, PropertyType, Tag } from '@/data/models';
import { deletedID, useDataStore } from '@/data/dataStore';
import { computeTagToInstance, deepCopy, isTag } from '@/utils/utils';
import { usePanopticStore } from '@/data/panopticStore';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import TagColumn from '@/components/tags/TagColumn.vue';
import TagTree from '@/components/tags/TagTree.vue';
import Modal2 from './Modal2.vue';
import TagImagesPreview from '../images/TagImagesPreview.vue';
import { useModalStore } from '@/data/modalStore';

const panoptic = usePanopticStore()
const data = useDataStore()

const propId = ref(-1)
// const tagId = ref(-1)
const selectedTagIds = ref<number[]>([])

const dragging = ref(false)
const view = ref('list')

const childDisabled = ref(false)
const parentDisbled = ref(false)

const tagToInstance = shallowRef<{ [tId: number]: Instance[] }>({})

const property = computed(() => {
    if (propId.value == -1 || !data.properties[propId.value]) {
        return undefined
    }
    const prop = data.properties[propId.value]
    if (!isTag(prop.type)) {
        return undefined
    }
    return prop
})
const properties = computed(() => data.propertyList.filter(p => isTag(p.type) && p.id != deletedID))
const tags = computed(() => data.tagList.filter(t => t.propertyId == property.value?.id))


const selectedTags = computed(() => selectedTagIds.value.map(tId => data.tags[tId]))

const propertyCounts = computed(() => {
    const res = {}
    for (let prop of properties.value) {
        const tags = data.tagList.filter(t => t.propertyId == prop.id)
        res[prop.id] = tags.reduce((a, b) => a + b.count, 0)
    }
    return res
})

// const tag = computed(() => {
//     if (tagId.value == -1 || !data.tags[tagId.value]) return undefined
//     const tag = data.tags[tagId.value]
//     if (property.value.id != tag.propertyId) return undefined
//     return tag
// })

const siblingsTags = computed(() => {
    const siblingSet = new Set<number>()
    parentTags.value.forEach(t => t.children.forEach(c => siblingSet.add(c)))
    const res = Array.from(siblingSet).filter(tId => !selectedTags.value.find(t => t.id == tId)).map(tId => data.tags[tId])
    return res.filter(t => t && t.id != deletedID)
})

const childrenTags = computed(() => {
    const childSet = new Set<number>()
    selectedTags.value.forEach(t => t.children.forEach(p => childSet.add(p)))
    return Array.from(childSet).map(p => data.tags[p]).filter(t => t && t.id != deletedID)
})

const parentTags = computed(() => {
    const parentSet = new Set<number>()
    selectedTags.value.forEach(t => t.parents.forEach(p => parentSet.add(p)))
    return Array.from(parentSet).map(p => data.tags[p]).filter(t => t && t.id != deletedID)
})

function show() {
    const init = useModalStore().getData(ModalId.TAG)
    if (init.propId != undefined) {
        propId.value = init.propId
    }
    if (init.tagId != undefined) {
        selectedTagIds.value = [init.tagId]
    }
    if (propId.value == -1 && properties.value.length) {
        propId.value = properties.value[0].id
    }

    updateTagToInstance()
}

function selectTags(selected: Tag[]) {
    selectedTagIds.value = selected.map(t => t.id)
}

function unselectTag(tagId: number) {
    selectedTagIds.value = selectedTagIds.value.filter(id => id != tagId)
}

function unselectTags() {
    selectedTagIds.value = []
}

function hide() {
    propId.value = -1
    selectedTagIds.value = []
}

async function addChild(tag: Tag) {
    const parentSet = new Set<number>(tag.parents)
    selectedTags.value.forEach(t => parentSet.add(t.id))
    const update = deepCopy(tag)
    update.parents = Array.from(parentSet)
    const commit = { tags: [update] }
    await data.sendCommit(commit)
}

async function addParent(tag: Tag) {
    const toUpdate = selectedTags.value.filter(t => !t.parents.find(p => p == tag.id)).map(deepCopy)
    toUpdate.forEach(t => t.parents.push(tag.id))
    const commit = { tags: toUpdate }
    await data.sendCommit(commit)

}

async function deleteTag(t: Tag) {
    const index = selectedTags.value.findIndex(tag => tag.id == t.id)
    if (index >= 0) {
        selectedTags.value.splice(index, 1)
    }
    await data.deleteTag(t.id)

}

async function removeTagParent(tag: Tag) {
    const toUpdate = selectedTags.value.filter(t => t.parents.find(p => p == tag.id)).map(deepCopy)
    toUpdate.forEach(t => { t.parents = t.parents.filter(p => p != tag.id) })
    const commit = { tags: toUpdate }
    await data.sendCommit(commit)
}

async function removeTagChild(tag: Tag) {
    const parentSet = new Set<number>()
    selectedTags.value.forEach(t => parentSet.add(t.id))
    const update = deepCopy(tag)
    update.parents = tag.parents.filter(p => !parentSet.has(p))
    const commit = { tags: [update] }
    await data.sendCommit(commit)
}


function onDrag(tag: Tag) {
    dragging.value = true
    if (!selectedTags.value.length) return

    const parentSet = new Set<number>()
    const childSet = new Set<number>()
    const selectedSet = new Set<number>()

    selectedTags.value.forEach(t => {
        selectedSet.add(t.id)
        t.allChildren.forEach(c => childSet.add(c))
        t.allParents.forEach(p => parentSet.add(p))
    })

    if (selectedSet.has(tag.id) || childSet.has(tag.id) || parentSet.has(tag.id)) {
        parentDisbled.value = true
        childDisabled.value = true
    }
}

async function createTag(name, parent) {
    const parents = parent == undefined ? undefined : [parent]
    data.addTag(property.value.id, name, parents)
}

async function createTagParent(name: string) {
    const newTag = buildTag(-1, propId.value, name)
    const update = selectedTags.value.map(deepCopy)
    update.forEach(t => { t.parents.push(newTag.id) })
    const commit = { tags: [newTag, ...update] }
    await data.sendCommit(commit)
}

async function createTagChildren(name: string) {
    const newTag = buildTag(-1, propId.value, name, selectedTagIds.value)
    const commit = { tags: [newTag] }
    await data.sendCommit(commit)
}

function onDragEnd() {
    dragging.value = false
    parentDisbled.value = false
    childDisabled.value = false
}

function updateTagToInstance() {
    tagToInstance.value = computeTagToInstance(data.instanceList, properties.value, data.tagList, data.tags)
}

async function mergeTags() {
    const list = selectedTagIds.value
    selectedTagIds.value = [list[0]]
    await data.mergeTags(list)
}


watch(tags, () => {
    updateTagToInstance()
    // data.tagList.forEach(t => {
    //     if (tagToInstance.value[t.id]) return
    //     tagToInstance.value[t.id] = []
    // })
})

</script>

<template>
    <Modal2 :id="ModalId.TAG" :title-style="1" @show="show" @hide="hide">
        <template #title>
            <div class="d-flex">
                <PropertyIcon class="property-option" :type="PropertyType.multi_tags" />
                <wTT message="modals.tags.list_view">
                    <div class="property-option bnr" :class="view == 'list' ? 'selected-property' : ''"
                        @click="view = 'list'"><i class="bi bi-list" /></div>
                </wTT>
                <wTT message="modals.tags.tree_view">
                    <div class="property-option bnr" :class="view == 'graph' ? 'selected-property' : ''"
                        @click="view = 'graph'"><i class="bi bi-diagram-3" /></div>
                </wTT>
                <div class="property-option" style="width: 31px;"></div>
                <div v-for="prop in properties" class="property-option bnr" @click="propId = prop.id"
                    :class="property?.id == prop.id ? 'selected-property' : ''">
                    <span>{{ prop.name }}</span>
                    <span class="ms-1 text-secondary">{{ propertyCounts[prop.id] }}</span>
                </div>
            </div>
        </template>
        <template #content="{ width, height }">
            <template v-if="property">
                <div class="d-flex h-100">
                    <div v-if="view == 'list'" class="h-100 bg-white d-flex">
                        <TagColumn :tags="tags" title="all" :main="true" :draggable="true" :selected-tags="selectedTags"
                            class="flex-shrink-0 flex-grow-0" @select="selectTags" @unselect="unselectTags"
                            @dragstart="onDrag" @dragend="onDragEnd" @create="createTag" @removed="deleteTag" />
                        <template v-if="selectedTags.length">
                            <TagColumn :tags="parentTags" title="parents" :draggable="dragging" @select="selectTags"
                                :selected-tags="selectedTags" class="flex-shrink-0 flex-grow-0"
                                :disabled="parentDisbled" @create="createTagParent" @added="addParent"
                                @removed="removeTagParent" />
                            <TagColumn :tags="siblingsTags" title="siblings" @select="selectTags" :draggable="false"
                                :selected-tags="selectedTags" class="flex-shrink-0 flex-grow-0" :disabled="dragging"
                                :no-create="true" />
                            <TagColumn :tags="childrenTags" title="children" :draggable="dragging" @select="selectTags"
                                :selected-tags="selectedTags" class="flex-shrink-0 flex-grow-0" @added="addChild"
                                :disabled="childDisabled" @create="createTagChildren" @removed="removeTagChild" />
                        </template>
                    </div>
                    <div v-if="view == 'graph'" :style="{ height: (height - 40) + 'px', width: '800px',position: 'relative' }"
                        style="overflow: hidden;" class="flex-shrink-0">
                        <TagTree :property="property" :selected-tags="selectedTags" @select="selectTags" @unselect="unselectTags"/>
                    </div>
                    <TagImagesPreview v-if="selectedTagIds.length" :tags="selectedTags" :tag-to-instance="tagToInstance"
                        @unselect="unselectTag" @merge="mergeTags"/>
                </div>
            </template>

        </template>
    </Modal2>
</template>

<style scoped>
.property-option {
    padding: 4px 8px;
    border-right: 1px solid var(--border-color);
}

.selected-property {
    background-color: white;
}
</style>