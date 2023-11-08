<script setup lang="ts">
import { globalStore } from '@/data/store';
import { computed } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';


const props = defineProps({
    propertyId: Number,
    value: Array<number>
})

const tags = computed(() => globalStore.tags[props.propertyId])
</script>

<template>
    <div class="text-nowrap text-secondary">
        <template v-if="props.value && props.value.length > 0">
            <span v-for="tagId in props.value">
                <TagBadge :tag="tags[tagId].value" :color="tags[tagId].color" class="me-1" />
            </span>
        </template>
        <template v-else>
            Add Tags...
        </template>

    </div>
</template>