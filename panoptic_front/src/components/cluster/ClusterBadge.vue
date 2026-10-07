<script setup lang="ts">
import { Colors, Score } from '@/data/models';
import { computed, PropType } from 'vue';

const props = defineProps({
    value: {required: true, type: Number},
    score: {type: Object as PropType<Score>}
})

const color = computed(() => {
    const s = props.score
    if (s && s.min != undefined && s.max != undefined && s.max > s.min) {
        const ratio = (s.value - s.min) / (s.max - s.min)
        const quality = s.maxIsBest ? ratio : 1 - ratio
        if (quality > 0.79) return 9
        if (quality > 0.44) return 10
        return 11
    }
    if(props.value < 21) return 9
    if(props.value < 56) return 10
    return 11
})

</script>

<template>
    <div class="badge tag-badge" :style="'background: ' + Colors[color].color">
      <span class="m-0 p-0 num">
        {{ props.value }}
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
  </style>