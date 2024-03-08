<script setup lang="ts">
import { CollectionManager } from '@/core/CollectionManager';
import { GroupManager } from '@/core/GroupManager';
import { defineProps, defineEmits } from 'vue'

const props = defineProps<{
    collection: CollectionManager
    height: number
}>()
const emits = defineEmits([])
</script>

<template>
  <div class="overflow-scroll" :style="{height: props.height+'px'}">
    <div>{{ props.collection.filterManager.state }}</div>
    <div>{{ props.collection.sortManager.state }}</div>
    <div>{{ props.collection.groupManager.state }}</div>
  </div>
</template>

<style scoped>
</style>