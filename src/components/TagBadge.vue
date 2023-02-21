<template>
  <div class="badge badge-dark m-1">
      <div class="d-flex align-items-center justify-content-between">
          <span class="pr-2">{{ tag }}</span>
          <i @click="$emit('deleteTag')" class="fa fa-times"></i>
      </div>
  </div>
</template>
  
<script setup>
const props = defineProps({
  tag: String
})
</script>
  
<style scoped>
</style>