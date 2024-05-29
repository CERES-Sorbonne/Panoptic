<script setup lang="ts">
import { computed, ref, triggerRef, watch } from 'vue'
import PropertyInput from '@/components/inputs/PropertyInput.vue';
import ColorPropInput from '@/components/inputs/ColorPropInput.vue';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import SelectCircle from '@/components/inputs/SelectCircle.vue';
import TextInput from '@/components/inputs/monoline/TextInput.vue';
import CheckboxPropInput from '@/components/inputs/CheckboxPropInput.vue';
import wTT from '../../tooltips/withToolTip.vue'
import DateInput from '@/components/inputs/monoline/DateInput.vue';
import TagPropInputDropdown from '@/components/tags/TagPropInputDropdown.vue';
import { Group, ImageIterator } from '@/core/GroupManager';
import { useProjectStore } from '@/data/projectStore';
import { ModalId, Property, PropertyRef, PropertyType, Image, Instance } from '@/data/models';
import { usePanopticStore } from '@/data/panopticStore';
import { keyState } from '@/data/keyState';
import { zoomModal } from '@/components/modals/zoomModal';
import Zoomable from '@/components/Zoomable.vue';
import { useDataStore } from '@/data/dataStore';
import { isTag } from '@/utils/utils';

const panoptic = usePanopticStore()
const store = useProjectStore()
const data = useDataStore()


const props = defineProps<{
    image: Instance,
    property: Property
    size: number
}>()

const emits = defineEmits(['resize', 'update:selected'])

const width = computed(() => props.size ?? 100)


const containerElem = ref(null)
const hover = ref(false)

</script>

<template>
    <div v-if="isTag(property.type)" class="d-flex"
        style="padding-top: 4px; padding-bottom: 4px;">
        <PropertyIcon :type="property.type" style="margin-right: 2px;" />
        <TagPropInputDropdown :property="props.property" :image="props.image" :can-create="true"
            :can-customize="true" :can-link="true" :can-delete="true" :auto-focus="true" :no-wrap="true"
            :width="(width - 22)" :teleport="true" />
    </div>
    <div v-else-if="property.type == PropertyType.color" class="d-flex flex-row">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <ColorPropInput class="mt-1 ms-0" :rounded="true" :image="image"
            :property="store.data.properties[property.id]" :width="width - 22" :min-height="20" />
    </div>
    <div v-else-if="property.type == PropertyType.string" class="d-flex flex-row">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <TextInput :property="store.data.properties[property.id]" :image="image" :width="width - 22"
            :height="26" />
    </div>
    <div v-else-if="property.type == PropertyType.number" class="d-flex flex-row">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <TextInput :property="store.data.properties[property.id]" :image="image" :width="width - 22"
            :height="26" :no-nl="true" />
    </div>
    <div v-else-if="property.type == PropertyType.url" class="d-flex flex-row">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <TextInput :property="store.data.properties[property.id]" :image="image" :width="width - 22"
            :height="26" :no-nl="true" />
    </div>
    <div v-else-if="property.type == PropertyType.checkbox" class="d-flex flex-row overflow-hidden">
        <CheckboxPropInput :property="store.data.properties[property.id]" :image="image" :width="width - 22"
            :min-height="26" />
        <div style="line-height: 26px; margin-left: 4px;">{{ store.data.properties[property.id].name }}
        </div>
    </div>
    <div v-else-if="property.type == PropertyType.date" class="d-flex flex-row" style="padding-top: 1px;">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <DateInput :property="store.data.properties[property.id]" :image="image" :width="width - 22"
            style="line-height: 25px;" />
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

img {
    max-height: 100%;
    max-width: 100%;
    /* width: auto;
    height: auto; */
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    margin: auto;
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