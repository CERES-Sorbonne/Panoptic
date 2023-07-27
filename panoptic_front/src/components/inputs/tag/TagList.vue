<script setup lang="ts">
import TagBadge from '@/components/tagtree/TagBadge.vue';
import { Tag } from '@/data/models';



const props = defineProps({
    tags: Array<Tag>
})

</script>

<template>
    <div>
        <TagBadge v-for="tag in props.tags" :tag="tag.value" :color="tag.color"/>
    </div>
</template>