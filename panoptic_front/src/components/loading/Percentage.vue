<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
    current: number
    max: number
    force?: boolean
}>()

const percentage = computed(() => {
    if(props.force) return '100%'
    if(props.max == 0) return '0%'
    if(props.current >= props.max) return '100%'
    return Math.floor(props.current / props.max * 100) + '%'
})

</script>

<template>
    <span>{{ percentage }}</span>
</template>

<style scoped>
</style>