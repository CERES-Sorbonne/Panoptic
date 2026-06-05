<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import wTT from '../../tooltips/withToolTip.vue'
import { ImageIterator } from '@/core/GroupManager'
import { ModalId, Property } from '@/data/models'
import { usePanopticStore } from '@/data/panopticStore'
import Zoomable from '@/components/Zoomable.vue'
import CenteredImage from '@/components/images/CenteredImage.vue'
import TreePropertyInput from './TreePropertyInput.vue'
import { useColumnStore } from '@/data/columnStore'
import { useInstanceStore } from '@/data/instanceStore.js'
import { useDataStore } from '@/data/dataStore'

const panoptic = usePanopticStore()
const store    = useColumnStore()
const data     = useDataStore()

const props = defineProps({
    image: { type: ImageIterator, required: true },
    size: { type: Number, default: 100 },
    index: Number,
    groupId: Number,
    hideProperties: Boolean,
    constraintWidth: Boolean,
    noBorder: Boolean,
    properties: Array<Property>,
    selected: Boolean,
    selectedPreview: Boolean
})

const emits = defineEmits(['resize', 'update:selected'])

// ── RESOLVE INSTANCE ID FROM SLOT ───────────────────────────────────────────
const instanceId = computed(() => store.instanceIds()[props.image.slot])

// Reactive per-instance property values (for TreePropertyInput).
// FIX 1: Provide a structural fallback value (-1) to keep the type checks happy before data streams in
const inst = computed(() => {
    const id = instanceId.value
    if (id === undefined || isNaN(id)) {
        return { id: -1, properties: {} }
    }
    return useInstanceStore().instanceData[id] ?? { id: id, properties: {}, baseUrl: '', sha1: '' }
})

const isSelected = computed(() => props.selected ?? false)

const hover    = ref(false)
const hideImg  = inject('hideImg')
const inputKey = inject('inputKey') as string

const score = computed(() => {
    const group = props.image.group
    if (!group.scores || instanceId.value === undefined) return undefined
    return group.scores.valueIndex[instanceId.value]
})
</script>

<template>
    <div
        class="full-container"
        :class="(!props.noBorder ? 'img-border' : '')"
        :style="`width: ${props.size + 2}px;`"
    >
        <Zoomable v-if="!hideImg && instanceId !== undefined" :image="inst">
            <div
                class="img-container"
                :style="`width: ${props.size + 2}px; height: ${props.size}px;`"
                @click="panoptic.showModal(ModalId.IMAGE, props.image)"
                @mouseenter="hover = true"
                @mouseleave="hover = false"
            >
                <div v-if="score != undefined" class="simi-ratio">{{ score }}</div>
                <CenteredImage
                    :instance-id="instanceId"
                    :width="props.size"
                    :height="props.size"
                    style="position: absolute; top: 0"
                />

                <div v-if="hover || isSelected" class="w-100 box-shadow"
                    :style="`width: ${props.size + 2}px; height: ${props.size}px;`" />
                <SelectCircle
                    v-if="hover || isSelected"
                    :model-value="isSelected"
                    @update:model-value="v => emits('update:selected', v)"
                    class="select"
                    :light-mode="true"
                />
            </div>
        </Zoomable>

        <!-- Spinner only while the instance base is still streaming; once loaded an
             unresolved slot means an empty group, so render nothing instead. -->
        <div v-else-if="!hideImg && !data.isLoaded"
            class="d-flex align-items-center justify-content-center bg-light text-muted border border-secondary-subtle"
            :style="`width: ${props.size + 2}px; height: ${props.size}px;`"
        >
            <div class="spinner-border spinner-border-sm text-secondary" role="status"></div>
        </div>

        <wTT v-if="props.image.sha1Group && props.image.sha1Group.slots?.length > 1"
            message="main.view.instances_tooltip" :click="false">
            <div class="image-count">{{ props.image.sha1Group.slots.length }}</div>
        </wTT>

        <div class="prop-container" v-if="props.properties.length && !props.hideProperties && instanceId !== undefined">
            <div v-for="property, index in props.properties" :key="property.id">
                <div class="custom-hr ms-2 me-2" v-if="index > 0"></div>
                <TreePropertyInput
                    :group-id="props.image.groupId"
                    :input-key="inputKey"
                    :property="property"
                    :instance="inst"
                    :width="props.size"
                    :idx="props.image.getImageOrder()"
                />
            </div>
        </div>

        <div v-if="props.selectedPreview" class="w-100 h-100"
            style="position: absolute; top: 0; left: 0; background-color: rgba(0, 0, 255, 0.127);" />
    </div>
</template>
<style scoped>
.image-count {
    position: absolute;
    top: 0;
    right: 0;
    padding: 0px 4px;
    background-color: var(--border-color);
    color: var(--grey-text);
    font-size: 10px;
    line-height: 15px;
    margin: 2px;
    border-radius: 5px;
    z-index: 100;
}

.simi-ratio {
    position: absolute;
    bottom: 0;
    right: 0;
    padding: 0px 4px;
    background-color: var(--border-color);
    color: var(--grey-text);
    font-size: 10px;
    line-height: 15px;
    margin: 2px;
    border-radius: 5px;
    z-index: 100;
}

.full-container {
    position: relative;
    background-color: white;
    margin-bottom: 7px;
    margin-right: 7px;
}

.img-border {
    border: 1px solid var(--border-color);
}

.img-container {
    position: relative;
    margin: auto;
    padding: auto;
    cursor: pointer;
}

.prop-container {
    width: 100%;
    border-top: 1px solid var(--border-color);
    padding: 2px;
    padding-top: 0px;
    padding-bottom: 0px;
    font-size: 12px;
}

.select {
    position: absolute;
    top: 0;
    left: 5px;
}

.box-shadow {
    position: relative;
}

.box-shadow::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    -webkit-box-shadow: inset 0px 24px 25px -20px rgba(0, 0, 0, 0.3);
    -moz-box-shadow: inset 0px 24px 25px -20px rgba(0, 0, 0, 0.3);
    box-shadow: inset 0px 50px 30px -30px rgba(0, 0, 0, 0.5);
    overflow: hidden;
}
</style>
