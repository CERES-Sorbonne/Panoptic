<script setup lang="ts">

const props = defineProps<{
    text?: string | number
}>()

</script>

<template>
  <div v-if="props.text" class="ellipsis">{{ props.text }}</div>
  <div v-else class="text-secondary">{{ $t('none') }}</div>
</template>

<style scoped>

.ellipsis {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

</style>