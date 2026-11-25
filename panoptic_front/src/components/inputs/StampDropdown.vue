<script setup lang="ts">
import { ImagePropertyValue, Instance, InstancePropertyValue, PropertyMode, PropertyType } from '@/data/models';
import StampForm from '../forms/StampForm.vue';
import { computed, inject, nextTick, reactive, ref } from 'vue';
import Dropdown, { dropdownRegistryKey } from '../dropdowns/Dropdown.vue';
import ViewModal from '../utils/ViewModal.vue';
import { viewModalScopeKey } from '@/data/composables/viewModal';
import { useDataStore } from '@/data/stores/dataStore';
import { useColumnStore } from '@/data/stores/columnStore';
import { useInstanceStore } from '@/data/stores/instanceStore';
import { useProjectStore } from '@/data/stores/projectStore';

const data = useDataStore()
const columnStore = useColumnStore()
const instanceStore = useInstanceStore()
const project = useProjectStore()

const props = defineProps<{
    images: Instance[] | (() => Instance[]),
    noBorder?: boolean,
    showNumber?: boolean
}>()

const emits = defineEmits(['stamped', 'show', 'hide'])

const stamp = reactive({}) as any
const erase = reactive(new Set()) as Set<number>
const modes = reactive({})
const dropdownElem = ref(null)

// Inside a view (or the top bar) the stamp form opens centered over the view area;
// elsewhere (image modal) it stays a dropdown.
const modalScope = inject(viewModalScopeKey, null)
const parentDropdown = inject(dropdownRegistryKey, null)
const modalOpen = ref(false)

function openModal() {
    clear()
    modalOpen.value = true
    emits('show')
}

function onModalClosed() {
    clear()
    emits('hide')
    parentDropdown?.hide()
}

function close() {
    clear()
    if (modalScope !== null) {
        if (modalOpen.value) {
            modalOpen.value = false
            onModalClosed()
        }
        return
    }
    dropdownElem.value?.hide()
}

function clear() {
    Object.keys(stamp).forEach((k: any) => delete stamp[k])
    erase.clear()
    nextTick(() => {
        if (dropdownElem.value && modalScope === null) {
            dropdownElem.value.focus()
        }
    })
}

// Image count for the header, only when it's free (a function may resolve a large selection).
const imageCount = computed(() => Array.isArray(props.images) ? props.images.length : null)

const applying = ref(false)

// Enter applies, except inside fields where Enter means something (tag input, text, number...).
// Ctrl/Cmd+Enter applies from anywhere.
function onEnter(e: KeyboardEvent) {
    if (e.isComposing) return
    const t = e.target as HTMLElement
    const inField = !!t.closest('input, textarea, select, button, [contenteditable=""], [contenteditable="true"]')
    if (inField && !(e.ctrlKey || e.metaKey)) return
    e.preventDefault()
    runApply()
}

async function runApply() {
    if (applying.value) return
    applying.value = true
    try { await apply() } finally { applying.value = false }
}

async function apply() {

    erase.forEach(k => stamp[k] = undefined)

    const instanceValues: InstancePropertyValue[] = []
    const imageValues: ImagePropertyValue[] = []

    const propIds = Object.keys(stamp).map(Number)
    const resolvedImages = typeof props.images === 'function' ? props.images() : props.images
    await instanceStore.ensureValues(resolvedImages.map(img => img.id), propIds)

    for (let propId of propIds) {
        for (let img of resolvedImages) {
            let stampValue = stamp[propId]
            const slot = columnStore.slotMap.get(img.id)
            if (slot === undefined) continue
            if (data.properties[propId].type == PropertyType.multi_tags && stampValue) {
                const oldTags = (instanceStore.instanceData[img.id]?.properties[propId] ?? [])
                if (!modes[propId]) {
                    stampValue = Array.from(new Set([...oldTags, ...stampValue]))
                }
                if (modes[propId] === 1) {
                    // do nothing, set values
                }
                if (modes[propId] === 2) {
                    const remove = new Set(stampValue)
                    stampValue = oldTags.filter(t => !remove.has(t))
                }

            }
            if (data.properties[propId].mode == PropertyMode.id) {
                const value: InstancePropertyValue = { propertyId: propId, instanceId: img.id, value: stampValue }
                instanceValues.push(value)
            } else {
                const value: ImagePropertyValue = { propertyId: propId, sha1: columnStore.sha1s()[slot], value: stampValue }
                imageValues.push(value)
            }
        }
    }
    await data.setPropertyValues(instanceValues, imageValues)
    close()
    // only a real stamp notifies the parent (the selection bar clears the selection on it)
    emits('stamped')
}

</script>

<template>
    <div class="m-0 p-0">
        <template v-if="modalScope !== null">
            <div @click="openModal">
                <slot name="button">
                    <div class="text-center" :class="{sbb: !props.noBorder, sb: props.noBorder}" style="width: 23px;">
                        <span v-if="props.showNumber"><i class="bi bi-paint-bucket" style="position: relative; left: 1px"></i></span>
                        <span v-else>{{ $t('modals.tagging.button') }}</span>
                    </div>
                </slot>
            </div>
            <ViewModal v-model:show="modalOpen" :scope="modalScope" :width="460" bare @close="onModalClosed">
                <div class="stm" @keydown.enter="onEnter">
                    <!-- Tool-window header: small-caps title + image count, close action -->
                    <div class="stm-head">
                        <span class="stm-title"><i class="bi bi-paint-bucket" />{{ $t('modals.tagging.button') }}</span>
                        <span v-if="imageCount !== null" class="stm-count">{{ imageCount }} {{ $t('main.group.images') }}</span>
                        <button type="button" class="stm-close" :title="$t('close')" @click="close">
                            <i class="bi bi-x-lg" />
                        </button>
                    </div>
                    <div class="stm-body">
                        <StampForm :values="stamp" :modes="modes" :erase="erase" />
                    </div>
                    <!-- Reset on the left, cancel / apply on the right -->
                    <div class="stm-foot">
                        <button type="button" class="stm-link" @click="clear">{{ $t('modals.tagging.clear') }}</button>
                        <div class="stm-actions">
                            <button type="button" class="stm-btn" @click="close">
                                {{ $t('modals.tagging.cancel') }}<kbd class="stm-key">Esc</kbd>
                            </button>
                            <button type="button" class="stm-btn stm-btn-primary" data-autofocus :disabled="applying" @click="runApply">
                                <span v-if="applying" class="spinner-border spinner-border-sm" role="status" />
                                {{ $t('modals.tagging.apply') }}<kbd class="stm-key">↵</kbd>
                            </button>
                        </div>
                    </div>
                </div>
            </ViewModal>
        </template>
        <Dropdown v-else ref="dropdownElem" :teleport="true" @show="emits('show')" @hide="emits('hide')">
            <template #button>
                <slot name="button">
                    <div class="text-center" :class="{sbb: !props.noBorder, sb: props.noBorder}" style="width: 23px;">
                        <span v-if="props.showNumber"><i class="bi bi-paint-bucket" style="position: relative; left: 1px"></i></span>
                        <span v-else>{{ $t('modals.tagging.button') }}</span>
                    </div>
                </slot>
            </template>
            <template #popup>
                <div @keydown.escape.prevent.stop="">
                    <div class="m-2" style="width: 400px; max-height: 400px; overflow-y: auto;">
                        <StampForm :values="stamp" :modes="modes" :erase="erase" @blur="dropdownElem.focus" />
                    </div>

                    <div class="d-flex pe-2 pb-2">
                        <div class="flex-grow-1"></div>
                        <div class="bbb me-2" @click="close">
                            {{ $t('modals.tagging.cancel') }}
                        </div>
                        <div class="bbb me-2" @click="clear">
                            {{ $t('modals.tagging.clear') }}
                        </div>
                        <div class="bbb me" @click="apply">
                            {{ $t('modals.tagging.apply') }}
                        </div>
                    </div>
                </div>
            </template>

        </Dropdown>
    </div>
</template>

<style scoped>
/* Modal presentation, same island tool-window look as ActionForm's modal (af-*): 30px
   small-caps header, 26px flat controls, 4px radii, no glow. CSS duplicated on purpose to
   keep the two components independent. No position/transform: non-teleported pickers
   inside StampForm are positioned against the view modal. */
.stm { display: flex; flex-direction: column; min-height: 0; max-height: 100%; color: var(--text-primary); font-size: 13px; cursor: default; }

.stm-head { flex: 0 0 auto; display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 4px 0 12px; }
.stm-title { display: inline-flex; align-items: center; gap: 6px; flex: 0 1 auto; min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.02em; }
.stm-title .bi { font-size: 13px; }
.stm-count { flex: 0 0 auto; font-size: 12px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.stm-close { flex: 0 0 auto; width: 22px; height: 22px; margin-left: auto; padding: 0; border: none; border-radius: var(--radius-sm) !important; background: none; color: var(--text-tertiary); font-size: 11px !important; }
.stm-close:hover { background-color: var(--hover-bg); color: var(--text-primary); }

/* Rows pad 8px themselves: names line up with the header title (12px). */
.stm-body { flex: 1 1 auto; min-height: 0; max-height: 60vh; overflow-y: auto; padding: 0 4px 8px; }
/* Title lives in the header now */
.stm-body :deep(.form-title) { display: none; }
.stm-body :deep(.stamp-table td) { padding-top: 4px; padding-bottom: 4px; }
.stm-body :deep(.prop-name) { font-size: 13px; }
.stm-body :deep(.prop-name.text-secondary) { color: var(--text-secondary) !important; }
.stm-body :deep(.prop-name-inner) { max-width: 150px; }
.stm-body :deep(input[type="text"]),
.stm-body :deep(input[type="number"]),
.stm-body :deep(textarea) { box-sizing: border-box; width: 100%; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: var(--bg-primary); }
.stm-body :deep(input[type="text"]:hover),
.stm-body :deep(input[type="number"]:hover),
.stm-body :deep(textarea:hover) { border-color: var(--border-dark); }
.stm-body :deep(input[type="text"]:focus),
.stm-body :deep(input[type="number"]:focus),
.stm-body :deep(textarea:focus) { outline: none; border-color: var(--primary); box-shadow: 0 0 0 1px var(--primary); }
.stm-body :deep(input[type="checkbox"]) { accent-color: var(--primary); }

.stm-foot { flex: 0 0 auto; display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-top: 1px solid var(--border-light); }
.stm-link { height: 26px; margin-left: -8px; padding: 0 8px; border: none; border-radius: var(--radius-sm) !important; background: none; font-size: 13px !important; color: var(--text-secondary); white-space: nowrap; }
.stm-link:hover { background-color: var(--hover-bg); color: var(--text-primary); }
.stm-actions { display: flex; gap: 6px; margin-left: auto; }
.stm-btn { gap: 6px; height: 26px; min-width: 72px; padding: 0 12px; border: 1px solid var(--border-color); border-radius: var(--radius-sm) !important; background: var(--bg-primary); font-size: 13px !important; color: var(--text-primary); white-space: nowrap; transition: background-color var(--transition-fast), border-color var(--transition-fast); }
.stm-btn:hover:not(:disabled) { background-color: var(--hover-bg); }
.stm-btn:focus-visible { border-color: var(--primary); box-shadow: 0 0 0 1px var(--primary); }
.stm-btn-primary { border-color: var(--primary); background: var(--primary); color: var(--text-inverse); }
.stm-btn-primary:hover:not(:disabled) { border-color: var(--primary-dark); background-color: var(--primary-dark); }
.stm-btn-primary:focus-visible { box-shadow: 0 0 0 1px var(--bg-primary), 0 0 0 2px var(--primary); }
.stm-key { display: inline-block; min-width: 16px; margin: 0 -4px 0 2px; padding: 0 4px; border: none; border-radius: 3px; background: var(--bg-tertiary); box-shadow: none; font-family: inherit; font-size: 11px; font-weight: 400; line-height: 16px; text-align: center; color: var(--text-tertiary); }
.stm-btn-primary .stm-key { background: rgba(255, 255, 255, 0.18); color: rgba(255, 255, 255, 0.85); }
.stm-btn-primary .spinner-border { width: 11px; height: 11px; border-width: 1.5px; }
</style>
