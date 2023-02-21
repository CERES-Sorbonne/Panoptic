<script setup>
  import {globalStore} from '../store'
  import {ref} from 'vue'

  let selectedImage = ref(null)
  let tagInput = ref("")

  const selectImage = (image) => {
    selectedImage.value = image;
    tagInput = '';
  }

  const closeSelectedImage = () => selectedImage.value = null;
</script>

<template>
  <div v-if="selectedImage" class="overlay" @click.self="closeSelectedImage()">
    <div class="selected-image-container">
      <img :src="selectedImage.url" class="selected-image">
    </div>
  </div>
  <div class="image-list">
    <div v-for="image in globalStore.images.slice(0,50)">
      <img class="image" :src="image.url" :key="image.name" @click="selectImage(image)"/>
    </div>
  </div>
</template>

<style scoped>
.image-list{
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 1rem;
}
.image{
  max-height: 200px;
}

.image:hover {
  cursor: pointer
}

.selected-image-container {
  z-index: 2;
  position: absolute;
  top: 50%;
  left: 65%;
  transform: translate(-50%, -50%);
  background-color: #fff;
  padding: 1rem;
  border-radius: 0.25rem;
  box-shadow: 0px 0px 5px 0px rgba(0, 0, 0, 0.5);
}

.selected-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1;
}
</style>
