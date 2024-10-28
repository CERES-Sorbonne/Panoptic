<script setup lang="ts">
import { keyState } from '@/data/keyState';
import { computed, ref } from 'vue';


const props = defineProps<{
  url?: string
}>()

const isHover = ref(false)
const urlMode = computed(() => keyState.ctrl && isHover.value)

function contentClick() {
    if (urlMode.value && props.url) {
        let url = props.url
        if (!url.startsWith('http')) {
            url = 'http://' + url
        }
        window.open(url, '_blank').focus()
    }
}

</script>

<template>
  <div v-if="props.url" class="ellipsis" :style="{
    cursor: urlMode ? 'pointer' : 'inherit',
    color: urlMode ? 'blue' : '',
  }" @mouseenter="isHover = true" @mouseleave="isHover = false" @click="contentClick">
    {{ props.url }}
  </div>
  <div v-else>None...</div>
</template>

<style scoped>
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>