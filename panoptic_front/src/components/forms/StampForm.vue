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


const props = defineProps({
    values: Object as () => { [propertyId: number]: any }
})

const properties = computed(() => {
    return globalStore.propertyList.filter(p => p.id >= 0)
})

function toggleProperty(id: number) {
    if(props.values[id] === undefined) {
        props.values[id] = propertyDefault(globalStore.properties[id].type)
    }
    else {
        delete props.values[id]
    }
}

</script>

<template>
    <table class="table">
        <b>{{$t('modals.tagging.title')}}</b>
        <tr v-for="property in properties">
            <template v-if="property.id >= 0">
                <td @click="toggleProperty(property.id)" style="cursor: pointer;" :class="(props.values[property.id] == undefined ? 'text-dimmed' : '')">{{ property.name }}</td>
                <td class="w-100">
                    <StandaloneTagInput v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag"
                        v-model="props.values[property.id]" :property="property" />
                    <StandaloneColorPropInput v-else-if="property.type == PropertyType.color" v-model="props.values[property.id]"/>
                    <TextInput
                            v-else-if="[PropertyType.string, PropertyType.number].some(t => t == property.type)"
                            :contenteditable="true" tag="div" :no-html="true" v-model="props.values[property.id]" :width="-1"
                            :min-height="20"
                            :no-nl="property.type == PropertyType.number" :url-mode="property.type == PropertyType.url"
                            :only-number="property.type == PropertyType.number" class="border rounded"/>
                    <StandaloneDateInput v-else-if="property.type == PropertyType.date" v-model="props.values[property.id]" />
                        <!-- <PropertyInput2 v-else :type="filterProperty.type" v-model="filter.value" /> -->
                    <StandalonePropertyInput v-else :type="property.type" v-model="props.values[property.id]" />
                </td>
            </template>
        </tr>
    </table>
</template>

