<script setup lang="ts">

const props = defineProps<{
  number?: number
  width?: number
}>()

</script>

<template>
  <div :style="{width: props.width? props.width + 'px': '100%'}">
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