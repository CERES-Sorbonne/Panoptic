<script setup lang="ts">
import { PropertyType, PropertyValue, Tag } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed } from 'vue';
import TagBadge from '../TagTree/TagBadge.vue';



const props = defineProps({
    value: Object as () => PropertyValue
})

const property = computed(() => globalStore.properties[props.value.propertyId])
const type = computed(() => property.value.type)

const isTag = computed(() => type.value == PropertyType.tag || type.value == PropertyType.multi_tags)

function mapTag(id: number): Tag[] {
    if (id == undefined) {
        return [{value: 'undefined', color: '#000000'} as Tag]
    }
    return [globalStore.tags[props.value.propertyId][id]]
}
</script>

<template>
    <div>
        <span>{{ property.name }}: </span>
        <span v-if="!isTag">{{ props.value.value }}</span>
        <span v-else>
            <span v-for="tag in mapTag(props.value.value)">
                <TagBadge :tag="tag.value" :color="tag.color" />
            </span>
        </span>
    </div>
</template>