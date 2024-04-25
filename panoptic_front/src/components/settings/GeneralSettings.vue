<script setup lang="ts">
import { defineProps, defineEmits, ref } from 'vue';
import TabMenu from '../TabMenu.vue';
import ActionSettings from '../ActionSettings.vue';
import { useProjectStore } from '@/data/projectStore';
import VectorSettings from './VectorSettings.vue';

const project = useProjectStore()
// const props = defineProps<{}>();

const categories = ref(['actions', 'vectors'])
const selectedCategory = ref(categories.value[0])

</script>

<template>
  <div class="row">
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