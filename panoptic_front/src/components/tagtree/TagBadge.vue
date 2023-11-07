<script setup lang="ts">
import { Colors } from '@/data/models';
import { computed } from 'vue';


const props = defineProps({
  tag: String,
  showDelete: { type: Boolean, default: false },
  color: Number
})


const color = computed(() => {
  if(props.color != undefined && props.color >= 0 && props.color < 12) {
    return Colors[props.color].color
  }
  return 'gray'
})

</script>


<template>
  <div class="badge tag-badge" :style="'background: ' + color">
    <span class="m-0 p-0">
      {{ tag }}
      <span v-if="showDelete" @click.prevent.stop="$emit('delete')" class="bi bi-x ms-1 tag-x"></span>
    </span>
  </div>
</template>
  
  
<style scoped>
.tag-badge {
  position: relative;
  top: -1px;
  margin: 0;
  padding: 3px 3px;
  border-radius: 5px !important;
  /* background: rgb(169, 169, 255); */
}

.tag-x:hover {
  cursor: pointer;
}

.number {
  transform: translate(-40%, -40%);
  font-size: 0.5rem;
}
</style>