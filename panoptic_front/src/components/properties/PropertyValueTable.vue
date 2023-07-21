<script setup lang="ts">
import { Image, PropertyType } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed, reactive } from 'vue';
import TagInput from '../inputs/TagInput.vue';
import { getImageProperties } from '@/utils/utils'
import PropertyInput from '../inputs/PropertyInput.vue';
import VGrid from "@revolist/vue3-datagrid";

const props = defineProps({
    images: Array<Image>
})

const columns = reactive([{
    prop: "name",
    name: "First",
},
{
    prop: "details",
    name: "Second",
}])
const rows = reactive([{
    name: "1",
    details: "Item 1",
},
{
    name: "2",
    details: "Item 2"
},
{
    name: "4",
    details: "Item 3"
},{
    name: "4",
    details: "Item 3"
},{
    name: "4",
    details: "Item 3"
},{
    name: "4",
    details: "Item 3"
},{
    name: "4",
    details: "Item 3"
},{
    name: "4",
    details: "Item 3"
},{
    name: "4",
    details: "Item 3"
}])

const properties = computed(() => globalStore.propertyList.filter(p => p.mode == 'id'))
const imageProperties = computed(() => props.images.map(img => img.id).map(getImageProperties))

</script>

<template>
    <table>
        <div style="height: 200px;">
            <VGrid theme="material" :source="rows" :columns="columns"/>
        </div>
        <!-- <tr>
            <th v-for="property in properties" class="no-wrap">{{ property.name }}</th>
        </tr>
        <tr v-for="imgProperties, imgIndex in imageProperties">
            <td v-for="property, propIndex in imgProperties">
                <TagInput v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag"
                    :property="property" :max-size="String(200)" :mono-tag="property.type == PropertyType.tag"
                    :input-id="[0, imgIndex, propIndex]" />
                <PropertyInput v-else :property="property" :max-size="String(200)" :input-id="[0, imgIndex, propIndex]" />
            </td>
        </tr> -->
    </table>
</template>