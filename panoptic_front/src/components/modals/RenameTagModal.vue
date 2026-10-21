<script setup lang="ts">
// Small rename prompt for a single tag, opened by cmd/ctrl-clicking any tag badge
// (see tagRenameShortcut). Modal data: { tagId }.
// Renaming to the name of another tag of the same property offers to merge into that tag instead.
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import Modal2 from './Modal2.vue'
import TagBadge from '@/components/tagtree/TagBadge.vue'
import { ModalId } from '@/data/models'
import { useDataStore } from '@/data/stores/dataStore'
import { useModalStore } from '@/data/stores/modalStore'
import { findSameNameTag } from '@/data/lib/tree'
import { installTagRenameShortcut, uninstallTagRenameShortcut } from '@/components/tags/tagRenameShortcut'

const data = useDataStore()
const modal = useModalStore()

const tagId = ref<number>()
const name = ref('')
const message = ref('')
// The tag already holding the typed name, once a save ran into it: confirming then merges.
const mergeTargetId = ref<number>()
const inputElem = ref<HTMLInputElement>()

function onShow(modalData: any) {
    tagId.value = modalData?.tagId
    name.value = data.tags[tagId.value]?.value ?? ''
    message.value = ''
    mergeTargetId.value = undefined
    // Modal2 focuses its own root on show; this runs after it and moves focus into the field.
    nextTick(() => {
        inputElem.value?.focus()
        inputElem.value?.select()
    })
}

async function save() {
    const tag = data.tags[tagId.value]
    if (!tag) return close()
    const value = name.value.trim()
    if (!value) {
        message.value = 'modals.rename_tag.empty'
        return
    }
    if (value === tag.value) return close()
    // Searched on submit rather than per keystroke: a property can hold many thousands of tags.
    const taken = findSameNameTag(data.tags, tag, value)
    if (taken) {
        mergeTargetId.value = taken.id
        return
    }
    close()
    await data.updateTag(tag.id, value)
}

// The existing tag comes first so it is the one kept, with its name, color and parents
// extended by the renamed tag's.
async function merge() {
    const tag = data.tags[tagId.value]
    const target = data.tags[mergeTargetId.value]
    close()
    if (!tag || !target) return
    await data.mergeTags([target.id, tag.id])
}

function confirm() {
    if (mergeTargetId.value !== undefined) merge()
    else save()
}

function onInput() {
    message.value = ''
    mergeTargetId.value = undefined
}

function close() {
    modal.closeModal(ModalId.RENAME_TAG)
}

onMounted(installTagRenameShortcut)
onUnmounted(uninstallTagRenameShortcut)
</script>

<template>
    <!-- Layer 1000 puts the modal (z-index 9000 + layer) above the #popup dropdown layer (9990),
         so renaming a tag shown inside an open dropdown isn't covered by it. -->
    <Modal2 :id="ModalId.RENAME_TAG" :layer="1000" :max-width="420" :max-height="140" @show="onShow">
        <template #title>
            <div class="d-flex align-items-center ps-1 title-row">
                <span class="me-2">{{ $t('modals.rename_tag.title') }}</span>
                <TagBadge v-if="data.tags[tagId]" :id="tagId" />
            </div>
        </template>
        <template #content>
            <div class="p-2">
                <input ref="inputElem" type="text" class="w-100" v-model="name"
                    :placeholder="$t('modals.rename_tag.placeholder')"
                    @keydown.enter.prevent="confirm" @input="onInput">
                <div v-if="mergeTargetId !== undefined" class="message text-warning d-flex align-items-center">
                    <span class="me-1">{{ $t('modals.rename_tag.exists') }}</span>
                    <TagBadge :id="mergeTargetId" class="me-1" />
                    <span>{{ $t('modals.rename_tag.merge_question') }}</span>
                </div>
                <div v-else class="message text-warning">{{ message && $t(message) }}</div>
                <div class="d-flex justify-content-end">
                    <div class="bbb me-2" @click="close">{{ $t('cancel') }}</div>
                    <div v-if="mergeTargetId !== undefined" class="bbb" @click="merge">{{ $t('modals.rename_tag.merge') }}</div>
                    <div v-else class="bbb" @click="save">{{ $t('confirm') }}</div>
                </div>
            </div>
        </template>
    </Modal2>
</template>

<style scoped>
input {
    border: 1px solid var(--border-color);
    border-radius: 3px;
    padding: 2px 6px;
}

.title-row {
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
}

.message {
    font-size: 12px;
    min-height: 18px;
    white-space: nowrap;
    overflow: hidden;
}
</style>
