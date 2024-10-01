<script setup lang="ts">
import { useDataStore } from '@/data/dataStore';
import { Tag } from '@/data/models';
import { deepCopy, sum } from '@/utils/utils';
import { defineProps, defineEmits, ref, nextTick } from 'vue'
import ColorDropdown from '../dropdowns/ColorDropdown.vue';

const data = useDataStore()

const props = defineProps<{
    tag: Tag
}>()
const emits = defineEmits(['unselect'])

const editTagName = ref(false)
const editTagInput = ref('')
const editTagNameInputElem = ref(null)

async function startEditName() {
    editTagInput.value = props.tag.value
    editTagName.value = true
    await nextTick()
    editTagNameInputElem.value.focus()
}

async function saveTagName() {
    let tag = deepCopy(props.tag)
    tag.value = editTagInput.value
    let commit = { tags: [tag] }
    await data.sendCommit(commit)
    if (editTagNameInputElem.value) {
        editTagNameInputElem.value.blur()
    }
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
        <div class="d-flex" v-if="!editTagName">
            <div v-if="!editTagName" class="text-nowrap overflow-hidden" @click="startEditName">
                {{ tag.value }}
            </div>
            <div v-else="editTagName">
                <input v-model="editTagInput" type="text" class="search-box" style="width: 100%; height: 20px;"
                    @blur="editTagName = false" @keypress.enter="saveTagName" ref="editTagNameInputElem" />
            </div>
            <div class="ms-1" style="padding-top: 2px;">
                <ColorDropdown :model-value="tag.color" @update:model-value="updateTagColor" />
            </div>
            <div class="ms-2 me-2 text-secondary">
                {{ tag.count + sum(tag.allChildren.map(c => data.tags[c].count)) }}
            </div>
            <div class="flex-grow-1"></div>
            <div class="bb me-1">
                <i class="bi bi-trash" @click="data.deleteTag(tag.id); emits('unselect', tag.id)" />
            </div>
            <div class="bb me-1">
                <i class="bi bi-x" @click="emits('unselect', tag.id)" />
            </div>

        </div>
        <div v-else-if="editTagName" class="d-flex" style="height: 25px;">
            <div class="me-1"><input v-model="editTagInput" type="text" class="search-box" style="width: 100%;"
                    @blur="editTagName = false" @keypress.enter="saveTagName" ref="editTagNameInputElem" /></div>
            <div style="padding-top: 2px;"><i class="bi bi-x bb" /></div>
            <div style="padding-top: 2px;" @mousedown="saveTagName"><i class="bi bi-check bb"></i></div>
        </div>


    </div>
</template>

<style scoped>
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