<script setup lang="ts">
import { useDataStore } from '@/data/stores/dataStore';
import { Tag } from '@/data/models';
import { deepCopy, sum } from '@/utils/utils';
import { findSameNameTag } from '@/data/lib/tree';
import { ref, nextTick } from 'vue'
import ColorDropdown from '../dropdowns/ColorDropdown.vue';
import TagBadge from '../tagtree/TagBadge.vue';

const data = useDataStore()

const props = defineProps<{
    tag: Tag
}>()
// merge: (keepId, removedId), when the new name is already another tag's and the user chose to merge
const emits = defineEmits(['unselect', 'merge'])

const editTagName = ref(false)
const editTagInput = ref('')
const editTagNameInputElem = ref<HTMLInputElement>(null)
// the tag already holding the typed name, once a save ran into it
const mergeTarget = ref<Tag>()

async function startEditName() {
    editTagInput.value = props.tag.value
    mergeTarget.value = undefined
    editTagName.value = true
    await nextTick()
    editTagNameInputElem.value.focus()
}

function stopEdit() {
    editTagName.value = false
    mergeTarget.value = undefined
}

async function saveTagName() {
    const value = editTagInput.value.trim()
    if (!value || value === props.tag.value) return stopEdit()
    const taken = findSameNameTag(data.tags, props.tag, value)
    if (taken) {
        mergeTarget.value = taken
        return
    }
    stopEdit()
    const tag = deepCopy(props.tag)
    tag.value = value
    await data.sendCommit({ tags: [tag] })
}

function confirm() {
    if (mergeTarget.value) merge()
    else saveTagName()
}

function merge() {
    const target = mergeTarget.value
    stopEdit()
    if (target) emits('merge', target.id, props.tag.id)
}

async function updateTagColor(color: number) {
    let tag = deepCopy(props.tag)
    tag.color = color
    let commit = { tags: [tag] }
    await data.sendCommit(commit)
}

</script>

<template>
    <div style="height: 37px; width: 100%;" class="tag-preview flex-shrink-0 ps-2 pt-1">
        <!-- One row in both states: the name and its input share the same box (.name), so the text
             does not move when editing starts. Buttons use mousedown.prevent to keep the input
             focused, since its blur ends the edit. -->
        <div class="d-flex align-items-center">
            <input v-if="editTagName" v-model="editTagInput" type="text" class="name name-input"
                @blur="stopEdit" @keydown.enter.prevent="confirm" @keydown.esc.stop="stopEdit"
                @input="mergeTarget = undefined" ref="editTagNameInputElem" />
            <div v-else class="name text-nowrap overflow-hidden" @click="startEditName">
                {{ tag.value }}
            </div>

            <template v-if="!editTagName">
                <div class="ms-1">
                    <ColorDropdown :model-value="tag.color" @update:model-value="updateTagColor" />
                </div>
                <div class="ms-2 me-2 text-secondary num">
                    {{ tag.count + sum(tag.allChildren.map(c => data.tags[c].count)) }}
                </div>
                <div class="flex-grow-1"></div>
                <div class="bb me-1">
                    <i class="bi bi-trash" @click="data.deleteTag(tag.id); emits('unselect', tag.id)" />
                </div>
                <div class="bb me-1">
                    <i class="bi bi-x" @click="emits('unselect', tag.id)" />
                </div>
            </template>
            <template v-else-if="mergeTarget">
                <div class="ms-2 text-warning text-nowrap">{{ $t('modals.rename_tag.exists') }}</div>
                <TagBadge :id="mergeTarget.id" class="ms-1 flex-shrink-0" />
                <div class="ms-2 bbb text-nowrap" @mousedown.prevent @click="merge">{{ $t('modals.rename_tag.merge') }}</div>
                <div class="ms-1 me-1 bb" @mousedown.prevent @click="stopEdit"><i class="bi bi-x" /></div>
            </template>
            <template v-else>
                <div class="ms-1 bb" @mousedown.prevent @click="stopEdit"><i class="bi bi-x" /></div>
                <div class="me-1 bb" @mousedown.prevent @click="saveTagName"><i class="bi bi-check" /></div>
            </template>
        </div>
    </div>
</template>

<style scoped>
.tag-preview {
    border-bottom: 1px solid var(--border-color);
}

/* Shared by the label and the input: same border width, padding and line box. The negative
   margin cancels the padding and border so the label text sits on the row's ps-2 edge. */
.name {
    box-sizing: border-box;
    height: 24px;
    line-height: 22px;
    padding: 0 4px;
    margin-left: -5px;
    border: 1px solid transparent;
    border-radius: 5px;
    cursor: text;
}

.name-input {
    flex: 1 1 0;
    min-width: 0;
    font: inherit;
    color: inherit;
    background: transparent;
    border-color: var(--border-color);
    outline: none;
}
</style>
