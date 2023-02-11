<script setup>
  import { RouterLink, RouterView } from 'vue-router'
  import { globalStore } from './store'
  import { onMounted } from 'vue'

  const getImages = async () => {
    const res = await fetch(`https://ceres.huma-num.fr/panoptic-back/images/`)
    const images = await res.json()
    globalStore.images = images[0]
  }

  onMounted(() => {
    getImages()
  })

</script>

<template>
  <RouterView />
</template>
