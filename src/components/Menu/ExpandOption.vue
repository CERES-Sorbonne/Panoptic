<script setup>
  import { ref, computed, defineProps } from 'vue';
  
  const props = defineProps({
    leftAlign: Boolean,
    titleSize: {type: String, default: 'h5'}
  });
  
  const expand = ref(true);
  
  const caretClass = computed(() => {
    let className = 'bi bi-caret-right btn-icon';
    if (expand.value) {
      className += ' expand';
    } else {
      className += ' hide';
    }
    return className;
  });
  
  function toggle() {
    expand.value = !expand.value;
  }
  </script>

<template>
    <div>
      <div :class="props.titleSize + ' m-1'" @click.stop="toggle">
        <span v-if="leftAlign" class="float-start">
          <span :class="caretClass"></span>
        </span>
        <slot name="name"></slot>
        <span class="float-end">
          <slot name="icons"></slot>
          <span v-if="!props.leftAlign" :class="caretClass"></span>
        </span>
      </div>
      <div v-show="expand" class="ms-2">
        <div class="">
            <slot name="content"> </slot>
        </div>
      </div>
    </div>
</template>
  
  <style>
  .bi-caret-right {
    display: inline-block;
    transition: 0.2s;
  }
  
  .bi-caret-right.expand {
    transform: rotate(90deg) !important;
  }
  
  .bi-caret-right.hide {
    transform: rotate(0deg) !important;
  }
  </style>
  