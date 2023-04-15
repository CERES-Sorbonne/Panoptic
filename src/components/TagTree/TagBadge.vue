<script setup lang="ts">

const props = defineProps({
  tag: String,
  number: Number,
  showDelete: { type: Boolean, default: false }
})
</script>


<template>
  <div class="badge rounded text-bg-primary me-1 tag-badge ps-1 pe-1">
  <!-- <div class="d-flex align-items-center justify-content-between"> -->
  <span class="m-0">
    {{ tag }}
    <span v-if="showDelete" @click="$emit('delete')" class="bi bi-x ms-1"></span>
  </span>
  <!-- <span v-if="number" class="position-absolute top-0 start-100 badge rounded-pill bg-danger number"> -->
  <!-- </span> -->
  <!-- </div> -->
  </div>
</template>
  
  
<style scoped>
.tag-badge {
  position: relative
}

.tag-badge:hover {
  cursor: pointer;
}

.number {
  transform: translate(-40%, -40%);
  font-size: 0.5rem;
}
</style>