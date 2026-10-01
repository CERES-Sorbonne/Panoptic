<script setup lang="ts">
import { ModalId } from '@/data/models';
import { usePanopticStore } from '@/data/stores/panopticStore';
import wTT from '@/components/tooltips/withToolTip.vue'

// Text input for a server path, with a button that opens the file explorer modal.
const props = defineProps<{
    modelValue?: string
    mode: 'folder' | 'file'
    width?: number
}>()

const emits = defineEmits(['update:modelValue'])

const panoptic = usePanopticStore()

function setPath(path?: string) {
    // The modal calls back with undefined when it is closed without a selection.
    if (!path) return
    emits('update:modelValue', path)
}

function browse() {
    panoptic.showModal(ModalId.FOLDERSELECTION, { callback: setPath, mode: props.mode })
}
</script>

<template>
    <div class="path-input" :style="{ width: props.width ? props.width + 'px' : undefined }">
        <input type="text" :value="props.modelValue"
            @input="emits('update:modelValue', ($event.target as HTMLInputElement).value)" />
        <wTT message="modals.fs.browse">
            <div class="browse" @click="browse">
                <i class="bi" :class="props.mode == 'folder' ? 'bi-folder2-open' : 'bi-file-earmark'" />
            </div>
        </wTT>
    </div>
</template>

<style scoped>
.path-input {
    display: flex;
    align-items: center;
    gap: 4px;
}

input {
    flex: 1;
    min-width: 0;
    font-size: 14px;
    line-height: 12px;
    padding: 2px 4px !important;
    border: 1px solid var(--border-color);
    border-radius: 3px;
}

.browse {
    cursor: pointer;
    padding: 0px 4px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
}

.browse:hover {
    background-color: var(--hover-bg);
}
</style>
