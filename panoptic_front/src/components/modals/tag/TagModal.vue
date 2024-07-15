<script setup lang="ts">
import { computed, ref } from 'vue'
import { ModalId, PropertyType } from '@/data/models';
import { useDataStore } from '@/data/dataStore';
import { isTag } from '@/utils/utils';
import { usePanopticStore } from '@/data/panopticStore';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import Modal2 from '../Modal2.vue';
import TagColumn from './TagColumn.vue';

const panoptic = usePanopticStore()
const data = useDataStore()

// const props = defineProps<{}>()
// const emits = defineEmits([])
const propId = ref(-1)
const tagId = ref(-1)
const dragging = ref(false)

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
const properties = computed(() => data.propertyList.filter(p => isTag(p.type)))
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
    if (tagId.value == -1 || !data.tags[tagId.value]) return
    const tag = data.tags[tagId.value]
    if (property.value.id != tag.propertyId) return
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
</script>

<template>
    <Modal2 :id="ModalId.TAG" :title-style="1" @show="show" @hide="hide">
        <template #title>
            <div class="d-flex">
                <PropertyIcon class="property-option" :type="PropertyType.multi_tags" />
                <div v-for="prop in properties" class="property-option bnr" @click="propId = prop.id"
                    :class="property?.id == prop.id ? 'selected-property' : ''">
                    <span>{{ prop.name }}</span>
                    <span class="ms-1 text-secondary">{{ propertyCounts[prop.id] }}</span>
                </div>
            </div>
        </template>
        <template #content="">
            <div class="h-100 bg-white d-flex" v-if="property">
                <TagColumn :tags="tags" title="Tout les tags" :main="true" :selected="tag" :draggable="true"
                    @select="e => tagId = e" @unselect="tagId = -1" @dragstart="dragging = true"
                    @dragend="dragging = false" />
                <template v-if="tag">
                    <TagColumn :tags="childrenTags" title="Tag enfants" :draggable="dragging" @select="e => tagId = e"
                        @added="addChild" />
                    <TagColumn :tags="siblingsTags" title="Tag siblings" @select="e => tagId = e"
                        :draggable="dragging" />
                    <TagColumn :tags="parentTags" title="Tag parents" :draggable="dragging" @select="e => tagId = e" />
                </template>

            </div>
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