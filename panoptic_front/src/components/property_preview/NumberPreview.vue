<script setup lang="ts">

const props = defineProps<{
  number?: number
}>()

</script>

<template>
  <div>
    <div v-if="props.number != undefined" class="ellipsis">{{ props.number }}</div>
    <div v-else>None...</div>
  </div>
</template>

<style scoped>
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>