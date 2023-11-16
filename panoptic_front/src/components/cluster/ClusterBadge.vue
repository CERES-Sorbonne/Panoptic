<script setup lang="ts">
import { computed } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';

const props = defineProps({
    value: {required: true, type: Number}
})

const color = computed(() => {
    if(props.value < 21) return 9
    if(props.value < 56) return 10
    return 11
})

</script>

<template>

    <TagBadge :tag="String(props.value)" :color="color" />

</template>