<script setup lang="ts">

const props = defineProps<{
    text?: string
}>()

</script>

<template>
  <div v-if="props.text" class="hidden">{{ props.text }}</div>
  <div v-else>None...</div>
</template>

<style scoped>

.hidden {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

</style>