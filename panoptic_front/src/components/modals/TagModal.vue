<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, watch } from 'vue'
import { Colors, Instance, ModalId, PropertyType, Tag } from '@/data/models';
import { deletedID, useDataStore } from '@/data/dataStore';
import { computeTagToInstance, deepCopy, isTag, sum } from '@/utils/utils';
import { usePanopticStore } from '@/data/panopticStore';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import ImagePreview from '@/components/preview/ImagePreview.vue';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import TagColumn from '@/components/tags/TagColumn.vue';
import TagTree from '@/components/tags/TagTree.vue';
import Modal2 from './Modal2.vue';

const panoptic = usePanopticStore()
const data = useDataStore()

// const props = defineProps<{}>()
// const emits = defineEmits([])
const propId = ref(-1)
const tagId = ref(-1)
const dragging = ref(false)
const view = ref('list')

const childDisabled = ref(false)
const parentDisbled = ref(false)

const editTagName = ref(false)
const editTagInput = ref('')
const editTagNameInputElem = ref(null)

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

const propertyCounts = computed(() => {
    const res = {}
    for (let prop of properties.value) {
        const tags = data.tagList.filter(t => t.propertyId == prop.id)
        res[prop.id] = tags.reduce((a, b) => a + b.count, 0)
    }
    return res
})

const tag = computed(() => {
    if (tagId.value == -1 || !data.tags[tagId.value]) return undefined
    const tag = data.tags[tagId.value]
    if (property.value.id != tag.propertyId) return undefined
    return tag
})

const siblingsTags = computed(() => {
    const res = []
    if (!tag.value) return res

    for (let parentId of tag.value.parents) {
        const parent = data.tags[parentId]
        for (let sibling of parent.children) {
            if (sibling != tag.value.id) {
                res.push(data.tags[sibling])
            }
        }
    }
    return res
})

const childrenTags = computed(() => {
    const res = []
    if (tag.value) {
        tag.value.children.forEach(t => res.push(data.tags[t]))
    }
    return res
})

const parentTags = computed(() => {
    const res = []
    if (tag.value) {
        tag.value.parents.forEach(t => res.push(data.tags[t]))
    }
    return res
})

function show() {
    const init = panoptic.modalData
    if (init.propId != undefined) {
        propId.value = init.propId
    }
    if (init.tagId != undefined) {
        tagId.value = init.tagId
    }
    if (propId.value == -1 && properties.value.length) {
        propId.value = properties.value[0].id
    }

    updateTagToInstance()
}

function hide() {
    propId.value = -1
    tagId.value = -1
}

function addChild(t) {
    if (t && tag.value) {
        data.addTagParent(t.id, tag.value.id)
    }
}

function addParent(t) {
    if (t && tag.value) {
        data.addTagParent(tag.value.id, t.id)
    }
}

async function deleteTag(t: Tag) {
    if (tag.value && tag.value.id == t.id) {
        tagId.value = -1
    }
    await data.deleteTag(t.id)

}

function removeTagParent(t: Tag) {
    data.deleteTagParent(tag.value.id, t.id)
}

function removeTagChild(t: Tag) {
    data.deleteTagParent(t.id, tag.value.id)
}


function onDrag(t: Tag) {
    dragging.value = true
    if (!tag.value) return
    console.log(t.id, tag.value.id, tag.value.allChildren, tag.value.allParents)
    if (t.id == tag.value.id || tag.value.allChildren.includes(t.id) || tag.value.allParents.includes(t.id)) {
        parentDisbled.value = true
        childDisabled.value = true
    }
}

async function createTag(name, parent) {
    const parents = parent == undefined ? undefined : [parent]
    data.addTag(property.value.id, name, parents)
}

async function createTagParent(name) {
    const currentTag = tag.value
    const newTag = await data.addTag(property.value.id, name, undefined)
    data.addTagParent(currentTag.id, newTag.id)

}

function onDragEnd() {
    dragging.value = false
    parentDisbled.value = false
    childDisabled.value = false
}

function updateTagToInstance() {
    tagToInstance.value = computeTagToInstance(data.instanceList, properties.value, data.tagList, data.tags)
}

async function startEditName() {
    editTagInput.value = data.tags[tagId.value].value
    editTagName.value = true
    await nextTick()
    editTagNameInputElem.value.focus()
}

async function saveTagName() {
    let tag = deepCopy(data.tags[tagId.value])
    tag.value = editTagInput.value
    let commit = { tags: [tag] }
    await data.sendCommit(commit)
    if (editTagNameInputElem.value) {
        editTagNameInputElem.value.blur()
    }
}
watch(tags, () => {
    data.tagList.forEach(t => {
        if (tagToInstance.value[t.id]) return
        tagToInstance.value[t.id] = []
    })
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
                <div v-if="view == 'list'" class="h-100 bg-white d-flex">
                    <TagColumn :tags="tags" title="all" :main="true" :selected="tag" :draggable="true"
                        class="flex-shrink-0 flex-grow-0" @select="e => tagId = e" @unselect="tagId = -1"
                        @dragstart="onDrag" @dragend="onDragEnd" @create="createTag" @removed="deleteTag" />
                    <template v-if="tag">
                        <TagColumn :tags="parentTags" title="parents" :draggable="dragging" @select="e => tagId = e"
                            class="flex-shrink-0 flex-grow-0" :disabled="parentDisbled" @create="createTagParent"
                            @added="addParent" @removed="removeTagParent" />
                        <TagColumn :tags="siblingsTags" title="siblings" @select="e => tagId = e" :draggable="false"
                            class="flex-shrink-0 flex-grow-0" :disabled="dragging" :no-create="true" />
                        <TagColumn :tags="childrenTags" title="children" :draggable="dragging" @select="e => tagId = e"
                            class="flex-shrink-0 flex-grow-0" @added="addChild" :disabled="childDisabled"
                            @create="name => createTag(name, tag.id)" @removed="removeTagChild" />
                        <div v-if="tagToInstance[tag.id].length" class="w-100 h-100 pt-1 d-flex flex-column">
                            <div style="height: 33px;" class="tag-preview flex-shrink-0 ps-2">
                                <div class="d-flex" style="padding-top: 2px;" v-if="!editTagName">
                                    <div v-if="!editTagName" @click="startEditName">
                                        {{ tag.value }}
                                    </div>
                                    <div v-else="editTagName">
                                        <input v-model="editTagInput" type="text" class="search-box"
                                            style="width: 100%;" @blur="editTagName = false"
                                            @keypress.enter="saveTagName" ref="editTagNameInputElem" />
                                    </div>
                                    <div class="ms-1" style="padding-top: 2px;">
                                        <div :style="{ backgroundColor: Colors[tag.color].color }"
                                            style="height: 20px;width: 20px; border-radius: 5px;"></div>
                                    </div>
                                    <div class="ms-2 me-2 text-secondary">
                                        {{ tag.count + sum(tag.allChildren.map(c => data.tags[c].count)) }}
                                    </div>
                                    <div class="flex-grow-1"></div>
                                    <div class="bb me-1">
                                        <i class="bi bi-trash" @click="data.deleteTag(tag.id); tagId = -1" />
                                    </div>
                                    <div class="bb me-1">
                                        <i class="bi bi-x" @click="tagId = -1" />
                                    </div>

                                </div>
                                <div v-else-if="editTagName" class="d-flex" style="height: 25px;">
                                    <div class="me-1"><input v-model="editTagInput" type="text" class="search-box"
                                            style="width: 100%;" @blur="editTagName = false"
                                            @keypress.enter="saveTagName" ref="editTagNameInputElem" /></div>
                                    <div style="padding-top: 2px;"><i class="bi bi-x bb" /></div>
                                    <div style="padding-top: 2px;" @mousedown="saveTagName"><i class="bi bi-check bb"></i></div>
                                </div>


                            </div>
                            <div class="flex-shrink-0" style="height: 2px;"></div>
                            <ImagePreview :instances="tagToInstance[tag.id]" />
                        </div>
                    </template>
                </div>
                <div v-if="view == 'graph'" :style="{ height: (height - 40) + 'px', position: 'relative' }"
                    style="overflow: hidden;">
                    <TagTree :property="property" />
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

.tag-preview {
    border-bottom: 1px solid var(--border-color);
}

.search-box {
    border: 1px solid var(--border-color);
    border-radius: 5px;
    overflow: hidden;
    padding: 1px 4px;
}
</style>