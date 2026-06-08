<script setup lang="ts">
import { ModalId } from '@/data/models';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { usePanopticStore } from '@/data/panopticStore';
import { useModalStore } from '@/data/modalStore';

const modal = useModalStore()
const panoptic = usePanopticStore()

const props = withDefaults(defineProps<{
    id: ModalId
    layer?: number
    maxWidth?: number
    maxHeight?: number
    noTitle?: boolean,
    titleStyle?: number
}>(), {
    layer: 0
})

const emits = defineEmits(['resize', 'show', 'hide'])
defineExpose({
    hide
})

const modalElem = ref(null)

const totalHeight = ref(0)
const totalWidth = ref(0)

const active = ref(false)
const modalWidth = computed(() => totalWidth.value - 56)
const modalHeight = computed(() => totalHeight.value - 56)

const titleStyle = computed(() => {
    if (!props.titleStyle) return 'title'
    if (props.titleStyle == 1) return 'title1'
})

const data = computed(() => panoptic.modalData)
const modalStyle = computed(() => {
    return { width: modalWidth.value + 'px', height: modalHeight.value + 'px' }
})
const bodyStyle = computed(() => {
    // return { maxWidth: modalWidth.value + 'px', height: modalHeight.value + 'px' }
    return { width: '100%', height: '100%', overflowY: 'auto' } as any
})

function hide() {
    if (active.value) {
        active.value = false
        emits('hide')
    }
}

function show() {
    active.value = true
    nextTick(() => modalElem.value.focus())
    emits('show', modal.layerOpen[props.layer].data)
}


function onWindowResize() {
    totalWidth.value = window.innerWidth
    totalHeight.value = window.innerHeight

    if (props.maxWidth && (props.maxWidth + 56) < totalWidth.value) { totalWidth.value = props.maxWidth + 56 }
    if (props.maxHeight && (props.maxHeight + 56) < totalHeight.value) { totalHeight.value = props.maxHeight + 56 }

    emits('resize', { height: totalHeight.value, width: totalWidth.value })
}

function close() {
    modal.closeModal(props.id)
}

onMounted(() => {
    window.addEventListener('resize', onWindowResize)
    onWindowResize()
    modal.registerModal(props.id, props.layer)
})

watch(() => modal.openIndex[props.id], (newVal, oldVal) => {
    if (newVal) {
        show()
        onWindowResize()
    }
    else if (active.value) {
        hide()
    }
})

</script>

<template>
    <div v-if="active" class="p-modal" :style="{zIndex: 9000 + (props.layer ?? 0)}" tabindex="-1" ref="modalElem" @click="panoptic.hideModal(props.id)"
        @keydown.esc="panoptic.hideModal(props.id)">
        <div class="d-flex w-100 h-100 justify-content-center align-items-center">
            <div class="modal-container" :style="modalStyle" @click.stop>
                <div class="modal-content d-flex flex-column h-100" v-if="active">
                    <div :class="titleStyle" v-if="!props.noTitle">
                        <div class="d-flex">
                            <div class="flex-grow-1">
                                <slot name="title"></slot>
                            </div>
                            <div class="close bi bi-x btn-icon" @click="panoptic.hideModal(props.id)"></div>
                        </div>
                    </div>
                    <div class="body flex-grow-1" :style="bodyStyle">
                        <slot name="content" :data="data" :width="modalWidth" :height="modalHeight" :hide="close"></slot>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>


<style scoped>
.modal-container {
    margin: 0px;
    background-color: var(--island-surface);
    overflow: hidden;
    border-radius: var(--radius-md) !important;
    border: 1px solid var(--island-border) !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.1);
}

.body {
    background-color: var(--island-surface);
    overflow: hidden;
}

.title {
    background-color: var(--bg-secondary);
    border-bottom: 1px solid var(--island-border);
    padding: 4px 4px;
}

.title1 {
    background-color: var(--bg-secondary);
    border-bottom: 1px solid var(--island-border);
}

.close {
    padding: 0 6px;
    display: flex;
    justify-content: center;
    align-items: center;
    color: var(--text-secondary);
    cursor: pointer;
}

.close:hover {
    color: var(--text-primary);
    background-color: var(--bg-tertiary);
}

.modal-content {
    padding: 0 !important;
    margin: 0 !important;
    overflow: hidden;
    border: none !important;
    border-radius: 0 !important;
}

.p-modal {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(2px);
}
</style>