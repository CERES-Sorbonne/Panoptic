<script setup lang="ts">

const props = defineProps<{
    loading: boolean
}>()
</script>

<template>
  <div v-if="props.loading">
    <div v-if="loading" class="spinner-border spinner-border-sm text-primary" style="position: relative; top: 1px"  strole="status">
            <span class="visually-hidden">Loading...</span>
        </div>
  </div>
</template>

<style scoped>
</style>