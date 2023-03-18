<script setup>
  import { ref, computed, defineProps } from 'vue';
  
  const props = defineProps({
    leftAlign: Boolean,
    small: String
  });
  
  const expand = ref(true);
  
  const caretClass = computed(() => {
    let className = 'bi bi-caret-right';
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
    <div @click.stop="toggle">
      <p :class="props.small ? 'h5' : 'h3'">
        <span v-if="leftAlign" class="float-start">
          <span :class="caretClass"></span>
        </span>
        <slot name="name"></slot>
        <span v-if="!props.leftAlign" class="float-end">
          <slot name="icons"></slot>
          <span :class="caretClass"></span>
        </span>
    </p>
      <div v-show="expand" class="ms-2">
        <div class="mt-3">
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
  