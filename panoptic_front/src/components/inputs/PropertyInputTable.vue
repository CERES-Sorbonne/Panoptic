<script setup lang="ts">
import { Instance, Property, PropertyMode, PropertyRef, PropertyType } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import wTT from '../tooltips/withToolTip.vue'
import PropertyIcon from '../properties/PropertyIcon.vue';
import PropInput from './PropInput.vue';
import TagBadge from '../tagtree/TagBadge.vue';
import { useDataStore } from '@/data/dataStore';

const project = useProjectStore()
const data = useDataStore()

const props = defineProps<{
    image: Instance
    properties: Property[]
    visibleProperties: {[id: number]: boolean}
}>()

const emits = defineEmits<{
    paint: [e: {instanceId: number, propertyId: number}]
}>()

function toggleProperty(property: Property) {
    if(!props.visibleProperties) return

    if(props.visibleProperties[property.id]) {
        delete props.visibleProperties[property.id]
    } else {
        props.visibleProperties[property.id] = true
    }
}
</script>

<template>
    <div class="main">
        <table class="table table-sm">
            <tbody class="main">
                <tr v-for="property in properties" class="">
                    <td class="text-nowrap">
                        <PropertyIcon :type="property.type" /> {{
                            data.properties[property.id].name }}
                    </td>
                    <td v-if="property.id > 0" class="ps-1 border-left" style="width: 100%;">
                        <PropInput v-if="property.id > 0" :property="data.properties[property.id]" :image="image"
                            :width="-1" :min-height="-1"/>
                    </td>
                    <td v-else class="border-left" colspan="2"  style="width: 100%;">
                        <p v-if="property.type != PropertyType._folders" class="m-0 p-0">{{ image.properties[property.id] }}</p>
                        <span v-else><TagBadge :tag="project.data.folders[image.properties[property.id]].name" :color="-1" /></span>
                    </td>

                    <td v-if="!property.computed" class="text-center btn-icon border-left"
                        style="padding: 4px 3px 0px 5px; width: 20px;" @click="emits('paint', {instanceId: props.image.id, propertyId: property.id})">
                        <wTT message="modals.image.fill_property_tooltip">
                            <i class="bi bi-paint-bucket"></i>
                        </wTT>
                    </td>

                    <td v-if="!property.computed && property.mode != PropertyMode.id" class="text-center btn-icon border-left" style="padding: 3px; width: 20px;"
                        @click="toggleProperty(property)">
                        <wTT message="modals.image.toggle_property_tooltip">
                            <i class="bi bi-eye" :class="(props.visibleProperties[property.id] ? 'text-primary' : '')" />
                        </wTT>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<style scoped>
.main {
    padding: 0px 0px;
    margin: 0;
}

td p {
    word-break: break-all;
}

.border-left {
    border-left: 1px solid var(--border-color);
}
</style>