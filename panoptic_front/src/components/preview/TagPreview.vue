<script setup lang="ts">
import { computed } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';
import { useStore } from '@/data/store2';

const store = useStore()

const props = defineProps({
    propertyId: Number,
    value: Array<number>
})

const tags = computed(() => store.data.properties[props.propertyId].tags)
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