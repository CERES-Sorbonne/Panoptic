<script setup lang="ts">
import { ref, computed, defineProps, onMounted } from 'vue';

const props = defineProps({
  leftAlign: Boolean,
  titleSize: { type: String, default: 'h5' },
  defaultExpand: { type: Boolean, default: true },
  resetOnHide: { type: Boolean, default: false }
});

const expand = ref(true);

const caretClass = computed(() => 'bi-chevron-right clickable ' + (expand.value ? 'expand' : 'hide'))

function toggle() {
  expand.value = !expand.value;
}

onMounted(() => {
  if (props.defaultExpand !== undefined) {
    expand.value = props.defaultExpand
  }
})
</script>

<template>
  <div>
    <div :class="props.titleSize">
      <span v-if="leftAlign" class="float-start">
        <span :class="caretClass" @click.stop="toggle"></span>
      </span>
      <slot name="name"></slot>
      <span class="float-end">
        <span style="margin-right: 3px;"><slot name="icons" ></slot></span>
        <span v-if="!props.leftAlign" :class="caretClass" @click.stop="toggle"></span>
      </span>
    </div>
    <!-- Use v-if to delete component n hide -->
    <template v-if="props.resetOnHide">
      <div v-if="expand" class="">
        <div class="">
          <slot name="content"> </slot>
        </div>
      </div>
    </template>
    <!-- DEFAULT BEHAVIOR -->
    <!-- User v-show to keep the element in dom and just hiding it when needed -->
    <template v-else>
      <div v-show="expand" class="">
        <div class="">
          <slot name="content"> </slot>
        </div>
      </div>
    </template>
  </div>
</template>
  
<style>
.bi-caret-right {
  display: inline-block;
  transition: 0.2s;
  margin-left: 0 !important;
}

.bi-caret-right.expand {
  transform: rotate(90deg) !important;
}

.bi-caret-right.hide {
  transform: rotate(0deg) !important;
}

.option-content{
  width: 100%
}
</style>
  
