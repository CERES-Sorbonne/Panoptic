<script setup lang="ts">

const props = defineProps<{
    number?: number
}>()

</script>

<template>
  <div v-if="props.number != undefined" class="hidden">{{ props.number }}</div>
  <div v-else>None...</div>
</template>

<style scoped>

.hidden {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

</style>