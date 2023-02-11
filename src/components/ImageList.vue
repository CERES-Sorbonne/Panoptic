
<script setup>
  import {globalStore} from '../store'
</script>

<template>
  <div class="image-list">
    <div v-for="image in globalStore.images.slice(0,50)">
      <img class="image" :src="globalStore.prefixUrl + image.name"/>
    </div>
  </div>
</template>

<style scoped>
  .image-list{
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
  }
  .image{
    max-height: 200px;
  }
</style>
