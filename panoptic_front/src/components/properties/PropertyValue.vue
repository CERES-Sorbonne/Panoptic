<script setup lang="ts">
import { PropertyType, PropertyValue, Tag } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed } from 'vue';
import TagBadge from '../TagTree/TagBadge.vue';
import { UNDEFINED_KEY } from '@/utils/groups';



const props = defineProps({
    value: Object as () => PropertyValue
})

const property = computed(() => globalStore.properties[props.value.propertyId])
const type = computed(() => property.value.type)

const isTag = computed(() => type.value == PropertyType.tag || type.value == PropertyType.multi_tags)

function mapTag(id: number | string): Tag[] {
    console.log(id)
    if (id == UNDEFINED_KEY) {
        console.log('go here')
        return [{value: 'indéfini', color: '#ced4da'} as Tag]
    }
    return [globalStore.tags[props.value.propertyId][id as number]]
}
</script>

<template>
    <div>
        <span>{{ property.name }}: </span>
        <span v-if="!isTag">
            <span v-if="props.value.value != UNDEFINED_KEY">{{ props.value.value }}</span>
            <span v-else class="text-secondary">indéfini</span>
        </span>
        <span v-else>
            <span v-for="tag in mapTag(props.value.value)">
                <TagBadge :tag="tag.value" :color="tag.color" />
            </span>
        </span>
    </div>
</template>