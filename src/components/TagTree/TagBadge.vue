<script setup lang="ts">

const props = defineProps({
  tag: String,
  number: Number,
  showDelete: { type: Boolean, default: false }
})
</script>


<template>
  <div class="badge rounded text-bg-primary me-1 tag-badge ps-1 pe-1">
    <span class="m-0">
      {{ tag }}
      <span v-if="showDelete" @click="$emit('delete')" class="bi bi-x ms-1 tag-x"></span>
    </span>
  </div>
</template>
  
  
<style scoped>
.tag-badge {
  position: relative
}

.tag-x:hover {
  cursor: pointer;
}

.number {
  transform: translate(-40%, -40%);
  font-size: 0.5rem;
}
</style>