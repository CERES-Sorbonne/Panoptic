<script setup lang="ts">
import { TabManager } from '@/core/TabManager';


const props = defineProps<{
    tab: TabManager
}>()
const emits = defineEmits([])
</script>

<template>
  <div>
    {{ props.tab.state.id }}
  </div>
</template>

<style scoped>
</style>