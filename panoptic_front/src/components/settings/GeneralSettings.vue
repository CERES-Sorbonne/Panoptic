<script setup lang="ts">
import ActionSettings from '../ActionSettings.vue';
import VectorSettings from './VectorSettings.vue';
import ProjectSettings from './ProjectSettings.vue';

</script>

<template>
  <div class="row">
    <div class="col category">
      <ProjectSettings />
    </div>
    <div class="col category">
      <ActionSettings />
    </div>
    <div class="col category">
      <VectorSettings />
    </div>
  </div>
</template>

<style scoped>

.category {
  margin: 10px;
}

</style>