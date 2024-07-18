<script setup lang="ts">
import { Colors } from '@/data/models';
import { computed } from 'vue';

const props = defineProps({
    value: {required: true, type: Number}
})

const color = computed(() => {
    if(props.value < 21) return 9
    if(props.value < 56) return 10
    return 11
})

</script>

<template>
    <div class="badge tag-badge" :style="'background: ' + Colors[color].color">
      <span class="m-0 p-0">
        {{ props.value }}
      </span>
    </div>
  </template>
    
    
  <style scoped>
  .tag-badge {
    /* position: relative; */
    /* top: -1px; */
    margin: 0;
    padding: 3px 3px;
    border-radius: 5px !important;
    /* background: rgb(169, 169, 255); */
  }
  
  .tag-x:hover {
    cursor: pointer;
  }
  </style>