<script setup lang="ts">
import { Image, Property, PropertyMode, PropertyType } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { computed, reactive } from 'vue';
import wTT from '../tooltips/withToolTip.vue'
import PropertyIcon from '../properties/PropertyIcon.vue';
import PropInput from './PropInput.vue';
import TagBadge from '../tagtree/TagBadge.vue';
const store = useProjectStore()

const props = defineProps<{
    image: Image
    properties: Property[]
}>()

const selectedProperties = reactive({})

function toggleProperty(property: Property) {

}

function paintSelection(property: Property) {

}

</script>

<template>
    <div class="main">
        <table class="table table-sm">
            <tbody class="main">
                <tr v-for="property in properties" class="">
                    <td class="text-nowrap">
                        <PropertyIcon :type="property.type" /> {{
                            store.data.properties[property.id].name }}
                    </td>
                    <td v-if="property.id > 0" class="ps-1 border-left">
                        <PropInput v-if="property.id > 0" :property="store.data.properties[property.id]" :image="image"
                            :width="-1" :min-height="20" />
                    </td>
                    <td v-else class="border-left" colspan="2">
                        <p v-if="property.type != PropertyType._folders" class="m-0 p-0">{{ image.properties[property.id].value }}</p>
                        <span v-else><TagBadge :tag="store.data.folders[image.properties[property.id].value].name" :color="-1" /></span>
                    </td>

                    <td v-if="property.id > 0" class="text-center btn-icon border-left"
                        style="padding: 4px 3px 0px 5px; width: 20px;" @click="paintSelection(property)">
                        <wTT message="modals.image.fill_property_tooltip">
                            <i class="bi bi-paint-bucket"></i>
                        </wTT>
                    </td>

                    <td class="text-center btn-icon border-left" style="padding: 3px; width: 20px;"
                        @click="toggleProperty(property)">
                        <wTT message="modals.image.toggle_property_tooltip">
                            <i class="bi bi-eye" :class="(selectedProperties[property.id] ? 'text-primary' : '')" />
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