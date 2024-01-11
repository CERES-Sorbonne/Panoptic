<script setup lang="ts">
import { Image, Property, PropertyMode } from '@/data/models';
import { useProjectStore } from '@/data/projectStore';
import { computed, reactive } from 'vue';
import wTT from '../tooltips/withToolTip.vue'
import PropertyIcon from '../properties/PropertyIcon.vue';
import PropInput from './PropInput.vue';
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
            <tbody>
                <tr v-for="property in properties" class="">
                    <template v-if="property.id >= 0">
                        <td class="text-nowrap">
                            <PropertyIcon :type="property.type" /> {{
                                store.data.properties[property.id].name }}
                        </td>
                        <td class="ps-1 border-left" style="width: 100%;">
                            <PropInput :property="store.data.properties[property.id]" :image="image" :width="-1"
                                :min-height="20" />
                        </td>

                        <td class="text-center btn-icon border-left" style="width: 20px;" @click="toggleProperty(property)">
                            <wTT message="modals.image.toggle_property_tooltip">
                                <i class="bi bi-eye" :class="(selectedProperties[property.id] ? 'text-primary' : '')" />
                            </wTT>
                        </td>


                        <td class="text-center btn-icon border-left" style="padding: 4px 2px 0px 5px; width: 20px;"
                            @click="paintSelection(property)">
                            <wTT message="modals.image.fill_property_tooltip">
                                <i class="bi bi-paint-bucket"></i>
                            </wTT>
                        </td>
                    </template>
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

.border-left {
    border-left: 1px solid var(--border-color);
}
</style>