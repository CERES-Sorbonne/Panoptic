<script setup lang="ts">
import TagBadge from '../tagtree/TagBadge.vue';


const props = defineProps({
    propertyId: Number,
    value: Array<number>
})

</script>

<template>
    <div class="text-nowrap text-secondary">
        <template v-if="props.value && props.value.length > 0">
            <span v-for="tagId in props.value">
                <TagBadge :id="tagId" class="me-1" />
            </span>
        </template>
        <template v-else>
            Add Tags...
        </template>

    </div>
</template>