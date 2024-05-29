<script setup lang="ts">
import { computed } from 'vue'
import ColorPropInput from '@/components/inputs/ColorPropInput.vue';
import PropertyIcon from '@/components/properties/PropertyIcon.vue';
import TextInput from '@/components/inputs/monoline/TextInput.vue';
import CheckboxPropInput from '@/components/inputs/CheckboxPropInput.vue';
import DateInput from '@/components/inputs/monoline/DateInput.vue';
import TagPropInputDropdown from '@/components/tags/TagPropInputDropdown.vue';
import { Property, PropertyType, Instance } from '@/data/models';
import { useDataStore } from '@/data/dataStore';
import { isTag } from '@/utils/utils';
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { useProjectStore } from '@/data/projectStore';

const data = useDataStore()
const project = useProjectStore()

const props = defineProps<{
    image: Instance,
    property: Property
    size: number
}>()

const emits = defineEmits(['resize', 'update:selected'])

const width = computed(() => props.size ?? 100)


</script>

<template>
    <div v-if="isTag(property.type)" class="d-flex" style="padding-top: 4px; padding-bottom: 4px;">
        <PropertyIcon :type="property.type" style="margin-right: 2px;" />
        <TagPropInputDropdown :property="props.property" :image="props.image" :can-create="true" :can-customize="true"
            :can-link="true" :can-delete="true" :auto-focus="true" :no-wrap="true" :width="(width - 22)"
            :teleport="true" />
    </div>
    <div v-else-if="property.type == PropertyType.color" class="d-flex flex-row">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <ColorPropInput class="mt-1 ms-0" :rounded="true" :image="image" :property="data.properties[property.id]"
            :width="width - 22" :min-height="20" />
    </div>
    <div v-else-if="property.type == PropertyType.string" class="d-flex flex-row">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <TextInput :property="data.properties[property.id]" :image="image" :width="width - 22" :height="26" />
    </div>
    <div v-else-if="property.type == PropertyType.number" class="d-flex flex-row">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <TextInput :property="data.properties[property.id]" :image="image" :width="width - 22" :height="26"
            :no-nl="true" />
    </div>
    <div v-else-if="property.type == PropertyType.url" class="d-flex flex-row">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <TextInput :property="data.properties[property.id]" :image="image" :width="width - 22" :height="26"
            :no-nl="true" />
    </div>
    <div v-else-if="property.type == PropertyType.checkbox" class="d-flex flex-row overflow-hidden">
        <CheckboxPropInput :property="data.properties[property.id]" :image="image" :width="width - 22"
            :min-height="26" />
        <div style="line-height: 26px; margin-left: 4px;">{{ data.properties[property.id].name }}
        </div>
    </div>
    <div v-else-if="property.type == PropertyType.date" class="d-flex flex-row" style="padding-top: 1px;">
        <PropertyIcon :type="property.type" style="line-height: 25px; margin-right:2px;" />
        <DateInput :property="data.properties[property.id]" :image="image" :width="width - 22"
            style="line-height: 25px;" />
    </div>
    <div v-else class="d-felx flex-row overflow-hidden text-nowrap" style="line-height: 26px;" >
        <PropertyIcon :type="property.type" style="margin-right: 3px;"/>
        <span v-if="property.type == PropertyType._folders">
            <TagBadge :tag="project.data.folders[data.instances[props.image.id].properties[props.property.id]].name" :color="-1" />
        </span>
        <span v-else>{{ data.instances[props.image.id].properties[props.property.id] }}</span>
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