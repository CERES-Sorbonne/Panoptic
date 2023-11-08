<script setup lang="ts">
import { PropertyType, propertyDefault } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed } from 'vue';

import StandaloneTagInput from '../inputs/StandaloneTagInput.vue';
import StandalonePropertyInput from '../inputs/StandalonePropertyInput.vue';
import StandaloneColorPropInput from '../inputs/StandaloneColorPropInput.vue';
import TextInput from '../inputs/TextInput.vue';
import DateInput from '../inputs/monoline/DateInput.vue';
import StandaloneDateInput from '../inputs/monoline/StandaloneDateInput.vue';
import StandaloneTextInput from '../inputs/multiline/StandaloneTextInput.vue';
import PropertyIcon from '../properties/PropertyIcon.vue';


const props = defineProps({
    values: Object as () => { [propertyId: number]: any }
})

const properties = computed(() => {
    return globalStore.propertyList.filter(p => p.id >= 0)
})

function toggleProperty(id: number) {
    if (props.values[id] === undefined) {
        props.values[id] = propertyDefault(globalStore.properties[id].type)
    }
    else {
        delete props.values[id]
    }
}

</script>

<template>
    <table class="table table-sm">
        <b>{{ $t('modals.tagging.title') }}</b>
        <tbody style="border-top: 1px solid var(--border-color)">
            <tr v-for="property in properties" style="min-height: 20px;">
                <template v-if="property.id >= 0">
                    <td @click="toggleProperty(property.id)" style="cursor: pointer;"
                        :class="(props.values[property.id] == undefined ? 'text-dimmed' : '')" class="text-nowrap">
                        <PropertyIcon :type="property.type" />
                        {{ property.name }}
                    </td>
                    <td class="w-100">
                        <StandaloneTagInput
                            v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag"
                            v-model="props.values[property.id]" :property="property" style="height: 25px; line-height: 20px;" />
                        <StandaloneColorPropInput v-else-if="property.type == PropertyType.color"
                            v-model="props.values[property.id]" style="height: 25px; line-height: 20px;" />
                        <StandaloneTextInput
                            v-else-if="[PropertyType.string, PropertyType.number, PropertyType.url].some(t => t == property.type)"
                            :no-html="true" v-model="props.values[property.id]" :width="-1" :min-height="20"
                            :no-nl="property.type == PropertyType.number" :url-mode="property.type == PropertyType.url"
                            :only-number="property.type == PropertyType.number" />
                        <StandaloneDateInput v-else-if="property.type == PropertyType.date"
                            v-model="props.values[property.id]" />
                        <!-- <PropertyInput2 v-else :type="filterProperty.type" v-model="filter.value" /> -->
                        <StandalonePropertyInput v-else :type="property.type" v-model="props.values[property.id]" style="height: 14px; line-height: 25px; margin-top: 4px;"/>
                    </td>
                </template>
            </tr>
        </tbody>
    </table>
</template>

