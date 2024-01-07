<script setup lang="ts">
import { Colors, PropertyType, PropertyValue, Tag } from '@/data/models';
import { computed } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';
import { UNDEFINED_KEY } from '@/core/GroupManager';
import { useProjectStore } from '@/data/projectStore';

const store = useProjectStore()

const props = defineProps({
    value: Object as () => PropertyValue
})

const property = computed(() => store.data.properties[props.value.propertyId])
const type = computed(() => property.value.type)

const isTag = computed(() => type.value == PropertyType.tag || type.value == PropertyType.multi_tags)


const color = computed(() => {
    if(props.value.value == undefined) return 'white'
    
    let value = Number(props.value.value)
    if(isNaN(value) || value > 12) return 'gray'
    return Colors[value].color
})

function mapTag(id: number | string): Tag[] {
    // console.log(id)
    if (id == undefined) {
        return [{value: '_indéfini', color: -1} as Tag]
    }
    return [store.data.properties[props.value.propertyId].tags[id as number]]
}
</script>

<template>
    <div class="d-flex text-nowrap " style="line-height: 25px;">
        <div class="me-1">{{ property.name }}: </div>
        <div v-if="property.type == PropertyType.color" :style="{backgroundColor: color}" class="color-holder">
        </div>
        <div v-else-if="property.type == PropertyType._folders">
            <TagBadge :tag="store.data.folders[props.value.value].name" :color="-1" />
        </div>
        <span v-else-if="property.type == PropertyType.date && props.value.value">{{ (props.value.value as Date).toLocaleDateString() }}</span>
        <span v-else-if="property.type == PropertyType.date"> undefined </span>
        <span v-else-if="!isTag">
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

<style scoped>
.color-holder {
    margin-top: 6px;
    height: 15px;
    width: 15px;
    border: 1px solid var(--border-color);
    border-radius: 5px;
}

</style>