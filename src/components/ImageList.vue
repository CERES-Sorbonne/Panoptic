<script setup>
  import {globalStore} from '../store'
  import {ref, watch, reactive, onMounted} from 'vue'

  import TagList from './TagList.vue'
  import TagBadge from './TagBadge.vue';


  let selectedImage = reactive(ref(null))
  let tagInput = ref("")
  
  const selectImage = (image) => {
    selectedImage.value = image;
    tagInput = '';
  }
  const closeSelectedImage = () => selectedImage.value = null;

  // est ce qu'on peut éviter d'utiliser ce watch ? probablement mon archi quiest pourrie (archi pourrie même hehehehehe)
  watch(
    globalStore,
    (newStore) => {
      if(!selectedImage.value){
        return
      }
      for(let image of newStore.images.slice(0,10)){
        if(image.name === selectedImage.value.name){
          selectImage(image)
          return
        }
      }
    })
</script>

<template>
  <div v-if="selectedImage" class="overlay" @click.self="closeSelectedImage()">
    <div class="selected-image-container">
      <img :src="selectedImage.url" class="selected-image">
      <tag-list :image="selectedImage"/>
    </div>
  </div>
  <div class="image-list">
    <div class="image-container" v-for="image in globalStore.images.slice(0,50)">
      <img class="image" :src="image.url" :key="image.name" @click="selectImage(image)"/>
      <div class="metadata-container">
        <tag-badge v-for="tag in image.tags" :tag="tag"/>
      </div>
    </div>
  </div>
</template>

<style scoped>
.image-list{
  display: flex;
  flex-wrap: wrap;
  /* gap: 0.5rem; */
  margin-top: 1rem;
}
.image{
  /* max-height: 200px; */
  height: 200px;
  object-fit: cover;
  max-width: 100%;
  min-width: 100%;
  vertical-align: bottom;
  /* margin: 0.1rem; */
}
.image-container{
  flex-grow: 1;
  margin: 2px;
  /* background-color: violet; */
  height: 250px;
}
.image:hover {
  cursor: pointer;
}

.metadata-container{
  background-color: rgb(255, 255, 255);
  height: 50px;
  border-bottom-right-radius: 15px;
  border-bottom-left-radius: 15px;
  border-color: rgb(207, 0, 0);
  border: solid 1px;
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
  /* height: 100%; */
  max-height: 60vh;
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
