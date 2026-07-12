<script setup lang="ts">
// Instance-based image cell. Unlike tree/Image.vue (which is hard-coupled to the
// ImageIterator class and its GroupManager), this takes a plain Instance so it can be
// used by ImageScroller.vue, which renders a flat instance list with no groups.
import { computed, inject, ref } from 'vue'
import SelectCircle from '@/components/inputs/SelectCircle.vue'
import { Property } from '@/data/models'
import Zoomable from '@/components/Zoomable.vue'
import CenteredImage from '@/components/images/CenteredImage.vue'
import TreePropertyInput from '@/components/scrollers/tree/TreePropertyInput.vue'
import { useInstanceStore } from '@/data/instanceStore.js'
import { useDataStore } from '@/data/dataStore'
import { Instance } from '@/data/models'

const data = useDataStore()

const props = defineProps<{
    instance: Instance
    size: number
    // Optional per-cell width (defaults to `size`). The scroller hands out 1px-wider
    // widths to some cells so a line fills its full width; height stays driven by `size`.
    width?: number
    properties: Property[]
    selected?: boolean
    // Flat index of this instance in the scroller's list — used for input focus ordering
    // (replaces ImageIterator.getImageOrder()).
    idx: number
}>()

const emits = defineEmits(['update:selected'])

const w = computed(() => props.width ?? props.size)

// Reactive per-instance data (property values live here, keyed by instance id).
const inst = computed(() => {
    const id = props.instance.id
    return useInstanceStore().instanceData[id] ?? { id, properties: {}, baseUrl: '', sha1: '' }
})

const isSelected = computed(() => props.selected ?? false)

const hover    = ref(false)
const hideImg  = inject('hideImg')
const inputKey = inject('inputKey') as string
</script>

<template>
    <div class="full-container img-border" :style="`width: ${w + 2}px;`">
        <Zoomable v-if="!hideImg" :image="inst">
            <div class="img-container image-drag-handle" :style="`width: ${w + 2}px; height: ${props.size}px;`"
                @mouseenter="hover = true" @mouseleave="hover = false">
                <CenteredImage :instance-id="props.instance.id" :width="w" :height="props.size"
                    style="position: absolute; top: 0" />

                <div v-if="hover || isSelected" class="w-100 box-shadow"
                    :style="`width: ${w + 2}px; height: ${props.size}px;`" />
                <SelectCircle v-if="hover || isSelected" :model-value="isSelected"
                    @update:model-value="v => emits('update:selected', v)" class="select" :light-mode="true" />
            </div>
        </Zoomable>

        <!-- Spinner only while the instance base is still streaming. -->
        <div v-else-if="!hideImg && !data.isLoaded"
            class="d-flex align-items-center justify-content-center bg-light text-muted border border-secondary-subtle"
            :style="`width: ${w + 2}px; height: ${props.size}px;`">
            <div class="spinner-border spinner-border-sm text-secondary" role="status"></div>
        </div>

        <div class="prop-container" v-if="props.properties.length">
            <div v-for="property, index in props.properties" :key="property.id">
                <div style="height: 1px;" v-if="index > 0"></div>
                <TreePropertyInput :group-id="0" :input-key="inputKey" :property="property" :instance="inst"
                    :width="props.size" :idx="props.idx" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.full-container {
    position: relative;
    background-color: white;
    margin-bottom: 7px;
    margin-right: 7px;
}

.img-border {
    border: 1px solid var(--border-color);
    border-radius: 3px;
}

.img-container {
    position: relative;
    margin: auto;
    padding: auto;
    cursor: pointer;
}

/* Only the image is the drag handle. Suppress text selection while grabbing it so
   dragging never highlights text; property inputs below keep normal selection. */
.image-drag-handle {
    user-select: none;
    -webkit-user-select: none;
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
