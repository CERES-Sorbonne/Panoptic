<script setup lang="ts">
import { NotifType } from '@/data/models';

const props = defineProps<{
    type: NotifType
}>()
const emits = defineEmits([])
</script>

<template>
    <i v-if="props.type == NotifType.DEBUG" class="bi bi-bug-fill text-primary" />
    <i v-if="props.type == NotifType.INFO" class="bi bi-info-circle-fill text-success" />
    <i v-if="props.type == NotifType.WARNING" class="bi bi-exclamation-triangle-fill text-warning" />
    <i v-if="props.type == NotifType.ERROR" class="bi bi-x-circle-fill text-danger" />
    
</template>

<style scoped>
</style>