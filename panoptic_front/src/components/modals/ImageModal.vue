<script setup lang="ts">
import { ModalId, PropertyType } from '@/data/models';
import { ShallowRef, computed, nextTick, provide, reactive, ref, shallowRef, watch } from 'vue';
import CenteredImage from '../images/CenteredImage.vue';
import ImageProperties from './image/ImageProperties.vue';
import ImageDisplay from './image/ImageDisplay.vue';
import PanelBox from './image/PanelBox.vue';
import Similarity from './image/Similarity.vue';
import Instances from './image/Instances.vue';
import SelectionStamp from '../selection/SelectionStamp.vue';
import wTT from '../tooltips/withToolTip.vue';
import { GroupManager, ImageIterator, SelectedImages } from '@/core/GroupManager';
import { usePanopticStore } from '@/data/panopticStore';
import { keyState } from '@/data/keyState';
import Modal2 from './Modal2.vue';
import { useDataStore } from '@/data/dataStore';
import { useModalStore } from '@/data/modalStore';
import { useColumnStore } from '@/data/columnStore';
import { useInstanceStore } from '@/data/instanceStore';
import InstanceData from '@/components/data/InstanceData.vue';
import { useResizeObserver } from '@vueuse/core';

const panoptic = usePanopticStore()
const data = useDataStore()
const modal = useModalStore()
const col = useColumnStore()
const instanceStore = useInstanceStore()

const groupManager = new GroupManager()

const PANELS_KEY = 'image_modal_panels'
const PROPERTIES_WIDTH = 400
const HISTORY_WIDTH = 140
// Height a bottom panel gets when there is room for it. Two open panels share the
// dock, which never eats more than two thirds of the modal.
const DOCK_PANEL_HEIGHT = 340
const DOCK_MAX_RATIO = 0.65

const historyElem = ref(null)
const centerElem = ref(null)
const centerHeight = ref(0)
const visibleProperties = reactive({})
const navigationHistory: ShallowRef<ImageIterator[]> = ref([])
const iterator: ShallowRef<ImageIterator> = ref(null)
const preview = shallowRef<SelectedImages>({})

// Which side panels are open. Nothing but the image by default; the choice is
// remembered so the modal reopens the way the user left it.
const panels = reactive({
    properties: false,
    similar: false,
    instances: false,
    history: true
})
loadPanels()

const active = computed(() => panoptic.openModalId == ModalId.IMAGE)

const currentInstanceId = computed(() => {
    if (!iterator.value?.isValid) return undefined
    return col.instanceIds()[iterator.value.slot]
})
const currentInstanceIds = computed(() => currentInstanceId.value !== undefined ? [currentInstanceId.value] : [])
const allPropIds = computed(() => data.propertyList.map(p => p.id))
const image = computed(() => instanceStore.instanceData[currentInstanceId.value])

const showHistory = computed(() => navigationHistory.value.length > 0)
const showHistoryPanel = computed(() => showHistory.value && panels.history)

const dockPanelCount = computed(() => (panels.similar ? 1 : 0) + (panels.instances ? 1 : 0))
const dockHeight = computed(() => {
    if (!dockPanelCount.value) return 0
    return Math.min(Math.round(centerHeight.value * DOCK_MAX_RATIO), dockPanelCount.value * DOCK_PANEL_HEIGHT)
})

// Global selection ids, reactive via selectionVersion.
const selectedIds = computed(() => {
    void col.selectionVersion
    return col.getSelectedIds()
})

provide('nextImage', nextImage)
provide('prevImage', prevImage)
provide('showHistory', showHistory)

useResizeObserver(centerElem, (entries) => {
    centerHeight.value = Math.floor(entries[0].contentRect.height)
})

function loadPanels() {
    try {
        const saved = JSON.parse(localStorage.getItem(PANELS_KEY) ?? '{}')
        Object.keys(panels).forEach(k => {
            if (typeof saved[k] == 'boolean') panels[k] = saved[k]
        })
    } catch (e) { /* corrupted or missing state: keep the defaults */ }
}

function togglePanel(key: string) {
    panels[key] = !panels[key]
    localStorage.setItem(PANELS_KEY, JSON.stringify(panels))
}

function closePanel(key: string) {
    panels[key] = false
    localStorage.setItem(PANELS_KEY, JSON.stringify(panels))
}

function onHover() {
    preview.value = {}
    const selectedIds = col.getSelectedIds()
    if (selectedIds.length) {
        selectedIds.forEach(i => preview.value[i] = true)
    } else if (groupManager.result.root) {
        const ids = col.instanceIds()
        groupManager.result.root.slots.forEach(s => preview.value[ids[s]] = true)
    }
}

function onHoverEnd() {
    preview.value = {}
}

function paint(propRef: { propertyId: number, instanceId: number }) {
    // Painting fills the similar images with a value: only meaningful while that panel is open.
    if (!panels.similar) return
    const property = data.properties[propRef.propertyId]
    const value = instanceStore.instanceData[propRef.instanceId]?.properties[property.id]
    if (value === undefined) return

    const ids = col.instanceIds()
    let instances = groupManager.result.root?.slots.map(s => instanceStore.instanceData[ids[s]]).filter(Boolean) ?? []
    const selectedIds = col.getSelectedIds()
    if (selectedIds.length) {
        instances = selectedIds.map(id => instanceStore.instanceData[id]).filter(Boolean)
    }
    if (property.type == PropertyType.multi_tags) {
        data.setTagPropertyValue(property.id, instances, value)
    } else {
        data.setPropertyValue(property.id, instances, value)
    }
    visibleProperties[property.id] = true
}

function onShow() {
    navigationHistory.value = []
    onModalDataChange(modal.getData(ModalId.IMAGE))
}

function onHide() {
    iterator.value = undefined
    navigationHistory.value = []
    groupManager.clearSelection()
}

async function onModalDataChange(value: ImageIterator) {
    if (panoptic.openModalId != ModalId.IMAGE) return

    if (iterator.value) {
        navigationHistory.value = [...navigationHistory.value, iterator.value]
        await nextTick()
        if (historyElem.value) {
            historyElem.value.scrollTop = historyElem.value.scrollHeight
        }

    }
    iterator.value = value
}

function nextImage() {
    const next = iterator.value.nextImages()
    if (next) {
        iterator.value = next
        clearNavigationHistory()
    }
}

function prevImage() {
    const prev = iterator.value.prevImages()
    if (prev) {
        iterator.value = prev
        clearNavigationHistory()
    }
}

function clearNavigationHistory() {
    navigationHistory.value = []
}

function rollback(index) {
    iterator.value = navigationHistory.value[index]
    navigationHistory.value.splice(index)
    navigationHistory.value = [...navigationHistory.value]
}

watch(() => modal.getData(ModalId.IMAGE), (data) => {
    if (iterator.value) {
        onModalDataChange(data)
    }
})
watch(() => keyState.left, (state) => {
    if (!active.value) return
    if (state && !showHistory.value) {
        prevImage()
    }
})
watch(() => keyState.right, (state) => {
    if (!active.value) return
    if (state && !showHistory.value) {
        nextImage()
    }
})
</script>

<template>
    <Modal2 :id="ModalId.IMAGE" @show="onShow" @hide="onHide">
        <template #title>
            <div class="d-flex align-items-center">
                <div class="d-flex">
                    <wTT message="modals.image.properties_tooltip">
                        <div class="panel-btn" :class="panels.properties ? 'active' : ''"
                            @click="togglePanel('properties')">
                            <i class="bi bi-card-list"></i>
                        </div>
                    </wTT>
                    <wTT message="modals.image.similar_images_tooltip">
                        <div class="panel-btn" :class="panels.similar ? 'active' : ''" @click="togglePanel('similar')">
                            <i class="bi bi-boxes"></i>
                        </div>
                    </wTT>
                    <wTT message="modals.image.unique_properties_tooltip">
                        <div class="panel-btn" :class="panels.instances ? 'active' : ''"
                            @click="togglePanel('instances')">
                            <i class="bi bi-layers"></i>
                        </div>
                    </wTT>
                    <wTT message="modals.image.history_tooltip" v-if="showHistory">
                        <div class="panel-btn" :class="panels.history ? 'active' : ''" @click="togglePanel('history')">
                            <i class="bi bi-clock-history"></i>
                        </div>
                    </wTT>
                </div>
                <div class="title-sep"></div>
                <div class="text-truncate"><b>ID: {{ image?.id }}</b> | {{ image?.width }} x {{ image?.height }} | {{
                    image?.name }}</div>
            </div>
        </template>
        <template #content>
            <InstanceData :instance-ids="currentInstanceIds" :prop-ids="allPropIds">
                <div class="d-flex h-100" v-if="image">
                    <div class="side-panel border-end" v-if="panels.properties"
                        :style="{ width: PROPERTIES_WIDTH + 'px' }">
                        <PanelBox :title="$t('modals.image.properties')" no-padding
                            @close="closePanel('properties')">
                            <ImageProperties :instance="image" :visible-properties="visibleProperties" @paint="paint"
                                @hover="onHover" @hoverEnd="onHoverEnd" />
                        </PanelBox>
                    </div>
                    <div class="center-col d-flex flex-column overflow-hidden" ref="centerElem">
                        <ImageDisplay :instance="image" :can-navigate="!showHistory && !!iterator" />
                        <div class="dock d-flex flex-column" v-if="dockHeight > 0"
                            :style="{ height: dockHeight + 'px' }">
                            <div class="dock-panel" v-if="panels.similar">
                                <PanelBox :title="$t('modals.image.similar_images')" @close="closePanel('similar')">
                                    <template #actions>
                                        <div v-if="selectedIds.length > 0" class="me-2">
                                            <SelectionStamp :selected-images-ids="selectedIds"
                                                @remove:selected="groupManager.clearSelection()"
                                                @stamped="groupManager.clearSelection()" />
                                        </div>
                                    </template>
                                    <template #default="{ width, height }">
                                        <Similarity :image="image" :width="width" :height="height"
                                            :similar-group="groupManager" :visible-properties="visibleProperties"
                                            :preview="preview" />
                                    </template>
                                </PanelBox>
                            </div>
                            <div class="dock-panel" v-if="panels.instances">
                                <PanelBox :title="$t('modals.image.unique_properties')"
                                    @close="closePanel('instances')">
                                    <template #default="{ width, height }">
                                        <Instances :image="image" :width="width" :height="height" />
                                    </template>
                                </PanelBox>
                            </div>
                        </div>
                    </div>
                    <div class="side-panel border-start" v-if="showHistoryPanel"
                        :style="{ width: HISTORY_WIDTH + 'px' }">
                        <PanelBox :title="$t('modals.image.history')" no-padding @close="closePanel('history')">
                            <div class="history text-center" ref="historyElem">
                                <div v-for="it, index in navigationHistory" class="bordered">
                                    <CenteredImage :instance-id="col.instanceIds()[it.slot]" :width="100" :height="100"
                                        @click="rollback(index)" />
                                </div>
                            </div>
                        </PanelBox>
                    </div>
                </div>
            </InstanceData>
        </template>
    </Modal2>
</template>

<style scoped>
.panel-btn {
    padding: 0 6px;
    line-height: 22px;
    border-radius: 3px;
    cursor: pointer;
    color: var(--text-secondary);
}

.panel-btn:hover {
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
}

.panel-btn.active {
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
}

.title-sep {
    border-left: 1px solid var(--border-color);
    height: 18px;
    margin: 0 8px;
}

.center-col {
    flex: 1 1 0;
    min-width: 0;
    min-height: 0;
}

.side-panel {
    height: 100%;
    flex-shrink: 0;
    overflow: hidden;
}

.dock {
    border-top: 1px solid var(--border-color);
    min-height: 0;
}

.dock-panel {
    flex: 1 1 0;
    min-height: 0;
}

.dock-panel+.dock-panel {
    border-top: 1px solid var(--border-color);
}

.history {
    background-color: var(--tab-grey);
    height: 100%;
    overflow-y: auto;
    padding: 10px 12px;
}

.bordered {
    border: 1px solid var(--border-color);
    background-color: white;
    width: 102px;
    height: 102px;
    margin-bottom: 10px;
}
</style>
