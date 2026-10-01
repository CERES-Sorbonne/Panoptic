<script setup lang="ts">
import { ref } from 'vue';
import FileExplorer from './FileExplorer.vue';
import Modal2 from './Modal2.vue';
import { usePanopticStore } from '@/data/stores/panopticStore';
import { ModalId } from '@/data/models';

const panoptic = usePanopticStore()

const props = defineProps<{ id: ModalId }>()

// Kept locally: the modal store drops the data as soon as the modal closes.
const data = ref(null as { mode?: string, callback?: (path?: string) => void })

function onShow(modalData) {
    data.value = modalData
}

// Closed without a selection: tell the caller with undefined.
function onHide() {
    const callback = data.value?.callback
    data.value = null
    if (callback) callback(undefined)
}

function select(path: string) {
    const callback = data.value?.callback
    data.value = null
    if (callback) callback(path)
    panoptic.hideModal(props.id)
}
</script>


<template>
    <!-- Modal2 gives the explorer a fixed height, so its columns scroll instead of growing the modal. -->
    <Modal2 :id="props.id" :layer="2" :max-width="1140" :max-height="700" @show="onShow" @hide="onHide">
        <template #title>
            <b v-if="data">{{ $t('modals.fs.' + (data.mode ?? 'images')) }}</b>
        </template>
        <template #content>
            <div class="h-100 overflow-hidden">
                <FileExplorer v-if="data" @select="select" :mode="data.mode" />
            </div>
        </template>
    </Modal2>
</template>
