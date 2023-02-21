<script setup>
  import { RouterLink, RouterView } from 'vue-router'
  import { globalStore } from './store'
  import { onMounted } from 'vue'

  onMounted(() => {
    globalStore.fetchImages()
  })

</script>

<template>
  <RouterView />
</template>
