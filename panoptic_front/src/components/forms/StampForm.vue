<script setup lang="ts">
import { PropertyType, propertyDefault } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed } from 'vue';

import StandaloneTagInput from '../inputs/StandaloneTagInput.vue';
import StandalonePropertyInput from '../inputs/StandalonePropertyInput.vue';
import StandaloneColorPropInput from '../inputs/StandaloneColorPropInput.vue';


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
        <b>{{$t('main.tagging.title')}}</b>
        <tr v-for="property in properties">
            <template v-if="property.id >= 0">
                <td @click="toggleProperty(property.id)" style="cursor: pointer;" :class="(props.values[property.id] == undefined ? 'text-dimmed' : '')">{{ property.name }}</td>
                <td class="w-100">
                    <StandaloneTagInput v-if="property.type == PropertyType.multi_tags || property.type == PropertyType.tag"
                        v-model="props.values[property.id]" :property="property" />
                    <StandaloneColorPropInput v-else-if="property.type == PropertyType.color" v-model="props.values[property.id]"/>
                    <StandalonePropertyInput v-else :type="property.type" v-model="props.values[property.id]" />
                </td>
            </template>
        </tr>
    </table>
</template>

