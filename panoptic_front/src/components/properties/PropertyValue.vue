<script setup lang="ts">
import { Colors, PropertyType, PropertyValue, Tag } from '@/data/models';
import { globalStore } from '@/data/store';
import { computed } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';
import { UNDEFINED_KEY } from '@/utils/groups';



const props = defineProps({
    value: Object as () => PropertyValue
})

const property = computed(() => globalStore.properties[props.value.propertyId])
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
        return [{value: 'indéfini', color: '#ced4da'} as Tag]
    }
    return [globalStore.tags[props.value.propertyId][id as number]]
}
</script>

<template>
    <div class="d-flex" style="line-height: 25px;">
        <div class="me-1">{{ property.name }}: </div>
        <div v-if="property.type == PropertyType.color" :style="{backgroundColor: color}" class="color-holder">
        </div>
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