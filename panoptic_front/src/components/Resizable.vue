<script setup lang="ts">
import { useResizeObserver } from '@vueuse/core';
import { computed, ref, onMounted, watch } from 'vue';


const props = defineProps({
    disabled: Boolean,
    startWidth: Number
})

const emits = defineEmits({
    'resize': Number,
})

const elem = ref(null)
const text = ref('')
const hover = ref(false) // should be used to activate resize only on hover but is anoying when dragging the cursor below the div during resize

const classes = computed(() => {
    const res = ['common']
    if(!props.disabled) { // always do right now to avoid using hover detection 
        res.push('horizontal')
    }
    return res
})

onMounted(() => {

    elem.value.style.width = props.startWidth + 'px'
    useResizeObserver(elem.value, (entries) => {
      const entry = entries[0]
      const { width, height } = entry.contentRect
      text.value = `width: ${width}, height: ${height}`
      // The element is border-box, so offsetWidth is exactly the width we set.
      // Emitting anything else (clientWidth, contentRect) makes the value drift
      // by the border/padding on every observer pass and the cell grows forever.
      const w = elem.value.offsetWidth
      if (w !== props.startWidth) emits('resize', w)
    })
})

watch(() => props.startWidth, () => elem.value.style.width = props.startWidth + 'px')

</script>

<template>
    <div :class="classes" ref="elem" @mouseenter="hover = true" @mouseout="hover = false">
        <!-- {{ text }} -->
        <slot></slot>
    </div>
</template>

<style scoped>

.common {
    overflow: hidden;
    box-sizing: border-box;
}

.horizontal {
    resize: horizontal;
}

</style>