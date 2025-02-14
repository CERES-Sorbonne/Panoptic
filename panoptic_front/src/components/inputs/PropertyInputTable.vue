<script setup lang="ts">
import { Instance, Property, PropertyMode, PropertyType } from '@/data/models';
import wTT from '../tooltips/withToolTip.vue'
import PropertyIcon from '../properties/PropertyIcon.vue';
import TagBadge from '../tagtree/TagBadge.vue';
import { useDataStore } from '@/data/dataStore';
import GridPropInput from '../scrollers/grid/GridPropInput.vue';
import { ref } from 'vue';

const data = useDataStore()

const props = defineProps<{
    image: Instance
    properties: Property[]
    visibleProperties: { [id: number]: boolean }
}>()

const emits = defineEmits<{
    paint: [e: { instanceId: number, propertyId: number }]
    hover
    hoverEnd
    toggleFilter: [e: number]
}>()

const inputElem = ref([])

function toggleProperty(property: Property) {
    if (!props.visibleProperties) return

    if (props.visibleProperties[property.id]) {
        delete props.visibleProperties[property.id]
    } else {
        props.visibleProperties[property.id] = true
    }
}

async function paint(index: number, propertyId: number) {
    await inputElem.value[index].waitForDbAction()
    emits('paint', { instanceId: props.image.id, propertyId: propertyId })
}
</script>

<template>
    <div class="main">
        <table class="table table-sm" style="margin-bottom: 0;table-layout: fixed;">
            <tbody class="main">
                <tr v-for="property, index in properties" class="" style="font-size: 14px;">
                    <td class="text-nowrap overflow-hidden" style="width: 100px !important;">
                        <PropertyIcon :type="property.type" />
                        <span class="text-wrap ms-1">
                            {{ data.properties[property.id].name }}
                        </span>
                    </td>
                    <td v-if="property.id > 0" class="ps-1 border-left" style="width: 100%;">
                        <GridPropInput v-if="property.id > 0" :property="data.properties[property.id]" :instance="image"
                            :width="-1" :min-height="property.type == PropertyType.color ? 24 : 20" ref="inputElem"/>
                    </td>
                    <td v-else class="border-left" colspan="2" style="">
                        <p v-if="property.type != PropertyType._folders" class="m-0 p-0">{{
                            image.properties[property.id] }}</p>
                        <span v-else>
                            <TagBadge :name="data.folders[image.properties[property.id]].name" :color="-1" />
                        </span>
                    </td>

                    <td v-if="!property.computed" class="text-center btn-icon border-left"
                        style="padding: 4px 3px 0px 5px; width: 24px;"
                        @click="paint(index, property.id)"
                        @mouseenter="emits('hover')" @mouseleave="emits('hoverEnd')">
                        <wTT message="modals.image.fill_property_tooltip">
                            <i class="bi bi-paint-bucket"></i>
                        </wTT>
                    </td>

                    <td v-if="!property.computed && property.mode != PropertyMode.id"
                        class="text-center btn-icon border-left" style="padding: 3px; width: 20px;"
                        @click="toggleProperty(property)">
                        <wTT message="modals.image.toggle_property_tooltip">
                            <i class="bi bi-eye"
                                :class="(props.visibleProperties[property.id] ? 'text-primary' : '')" />
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