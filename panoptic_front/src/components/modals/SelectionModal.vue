<script setup lang="ts">
// Shows every currently selected image in a flat, virtualized wall.
// Opened from SelectionStamp's image button with { ids } as modal data. The scroller uses
// the *global* selection namespace — the one every SelectionStamp caller reads — so cells
// render as selected and unchecking one really removes it from the selection. The id list
// itself is snapshotted on show, so deselecting doesn't make images vanish under the cursor.
import { ref } from 'vue'
import Modal2 from './Modal2.vue'
import ImageScroller from '@/components/scrollers/image/ImageScroller.vue'
import RangeInput from '@/components/inputs/RangeInput.vue'
import { Instance, ModalId } from '@/data/models'
import { useDataStore } from '@/data/dataStore'

const data = useDataStore()

const instances = ref<Instance[]>([])
const imageSize = ref(100)

// Same fallback as SelectionStamp: a selection can hold instances no visible component
// registered, so stub the missing ones — ImageScroller loads their data by id anyway.
function onShow(modalData: any) {
    const ids: number[] = modalData?.ids ?? []
    instances.value = ids.map(id => data.instances[id] ?? ({ id } as any))
}

function onHide() {
    instances.value = []
}
</script>

<template>
    <Modal2 :id="ModalId.SELECTION" @show="onShow" @hide="onHide">
        <template #title>
            <div class="d-flex align-items-center ps-2">
                <span class="me-3">{{ instances.length }} selected images</span>
                <div class="d-flex align-items-center">
                    <div class="bi bi-aspect-ratio me-1" />
                    <RangeInput :min="60" :max="250" v-model="imageSize" />
                </div>
            </div>
        </template>
        <template #content="{ width, height }">
            <div class="p-2">
                <ImageScroller input-key="selection-modal" :instances="instances"
                    :properties="[]" :image-size="imageSize" :width="width-8" :height="height - 52" :no-drag="true" />
            </div>
        </template>
    </Modal2>
</template>
